# coding=utf-8
import ast
import copy
import runpy
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
MOB_ROOT = ROOT / "src" / "SwordSoul_NewERA_B" / "SwordSoulMobFightScripts"


def read_source(relative_path):
    return (MOB_ROOT / relative_path).read_text(encoding="utf-8-sig")


def class_assignment(relative_path, class_name, assignment_name):
    tree = ast.parse(read_source(relative_path), str(MOB_ROOT / relative_path))
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            for child in node.body:
                if isinstance(child, ast.Assign):
                    for target in child.targets:
                        if isinstance(target, ast.Name) and target.id == assignment_name:
                            return ast.literal_eval(child.value)
    raise AssertionError("missing %s.%s" % (class_name, assignment_name))


def without_ranges(component_data):
    data = copy.deepcopy(component_data)
    data.pop("within_radius", None)
    for entry in data.get("entity_types", []):
        entry.pop("max_dist", None)
        entry.pop("within_default", None)
    return data


def build_selector_lifecycle_harness(build_func):
    tree = ast.parse(read_source("Entities/BaseMob.py"), str(MOB_ROOT / "Entities" / "BaseMob.py"))
    method_names = {
        "SnapshotIntellectJsonTargetSelector",
        "RestoreIntellectJsonTargetSelector",
        "SyncIntellectJsonTargetSelector",
    }
    methods = []
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == "SwordSoulMobEntity":
            methods.extend(
                child for child in node.body
                if isinstance(child, ast.FunctionDef) and child.name in method_names
            )
    assert {node.name for node in methods} == method_names
    harness_node = ast.ClassDef(
        name="SelectorLifecycleHarness",
        bases=[ast.Name(id="object", ctx=ast.Load())],
        keywords=[],
        body=methods,
        decorator_list=[],
    )
    module = ast.Module(body=[harness_node], type_ignores=[])
    ast.fix_missing_locations(module)
    namespace = {
        "copy": copy,
        "BuildIntellectTargetSelectorData": build_func,
    }
    exec(compile(module, "<selector-lifecycle-harness>", "exec"), namespace)
    harness = namespace["SelectorLifecycleHarness"]

    def get_components(self):
        return self.components

    def get_template(self):
        return self.IntellectJsonTargetSelectorTemplate

    def remove_component(self, name):
        self.components.pop(name, None)
        return True

    def add_component(self, name, data):
        self.components[name] = copy.deepcopy(data)
        return True

    harness.GetEffectiveComponentsForIntellectTargetSelector = get_components
    harness.GetIntellectJsonTargetSelectorTemplate = get_template
    harness.remove_actor_component = remove_component
    harness.add_actor_component = add_component
    return harness


def new_lifecycle_instance(harness, template, components, detect_range, memory_time, support_map=None,
                           requires_original=False):
    instance = harness()
    instance.IntellectJsonTargetSelectorEnabled = True
    instance.IntellectJsonTargetSelectorComponentName = "minecraft:behavior.nearest_attackable_target"
    instance.IntellectJsonTargetSelectorTemplate = copy.deepcopy(template)
    instance.IntellectJsonTargetSelectorRequiresOriginal = requires_original
    instance.IntellectJsonTargetSupportComponentMap = copy.deepcopy(support_map or {})
    instance.IntellectJsonTargetSelectorSnapshotReady = False
    instance.IntellectJsonTargetSelectorHadOriginal = False
    instance.IntellectJsonTargetSelectorOriginalData = None
    instance.IntellectJsonTargetSupportOriginalDataMap = {}
    instance.IntellectJsonTargetSelectorApplied = False
    instance.components = copy.deepcopy(components)
    intellect = type("Intellect", (), {
        "detectRange": detect_range,
        "pursuitMemoryTime": memory_time,
    })()
    instance.ai_core = type("AICore", (), {"intellect": intellect})()
    return instance


def test_intellect_ranges_drive_json_selector():
    intellect = runpy.run_path(str(MOB_ROOT / "AI" / "Intellect.py"))
    presets = intellect["INTELLECT_PRESETS"]
    assert presets["low"]["detectRange"] == 12.0
    assert presets["mid"]["detectRange"] == 18.0
    assert presets["high"]["detectRange"] == 24.0
    assert presets["max"]["detectRange"] == 28.0

    helper = runpy.run_path(str(MOB_ROOT / "AI" / "TargetSelector.py"))
    build = helper["BuildIntellectTargetSelectorData"]

    ravager = class_assignment("Entities/RavagerMob.py", "RavagerMob", "IntellectJsonTargetSelectorTemplate")
    ravager_original = copy.deepcopy(ravager)
    ravager_result = build(ravager, presets["mid"]["detectRange"], presets["mid"]["pursuitMemoryTime"])
    assert ravager == ravager_original
    assert ravager_result["within_radius"] == 18.0
    assert [entry["max_dist"] for entry in ravager_result["entity_types"]] == [18.0, 18.0]
    assert without_ranges(ravager_result) == without_ranges(ravager_original)

def test_warden_preserves_native_anger_target_chain():
    # Codex 2026-08-10: 原版监守者没有 nearest_attackable_target，禁止再为智力距离拆装 anger_level。
    assert class_assignment(
        "Entities/WardenMob.py", "WardenMob", "IntellectJsonTargetSelectorEnabled"
    ) is False
    assert class_assignment(
        "Entities/WardenMob.py", "WardenMob", "IntellectJsonTargetSelectorTemplate"
    ) is None
    assert class_assignment(
        "Entities/WardenMob.py", "WardenMob", "IntellectJsonTargetSupportComponentMap"
    ) == {}


def test_selector_lifecycle_restores_original_components():
    intellect = runpy.run_path(str(MOB_ROOT / "AI" / "Intellect.py"))
    presets = intellect["INTELLECT_PRESETS"]
    helper = runpy.run_path(str(MOB_ROOT / "AI" / "TargetSelector.py"))
    build = helper["BuildIntellectTargetSelectorData"]
    harness = build_selector_lifecycle_harness(build)
    component_name = "minecraft:behavior.nearest_attackable_target"

    ravager_template = class_assignment(
        "Entities/RavagerMob.py",
        "RavagerMob",
        "IntellectJsonTargetSelectorTemplate",
    )
    ravager = new_lifecycle_instance(
        harness,
        ravager_template,
        {component_name: ravager_template},
        presets["mid"]["detectRange"],
        presets["mid"]["pursuitMemoryTime"],
        requires_original=True,
    )
    assert ravager.SyncIntellectJsonTargetSelector(True) is True
    assert ravager.components[component_name]["within_radius"] == 18.0
    assert ravager.SyncIntellectJsonTargetSelector(False) is True
    assert ravager.components[component_name] == ravager_template

def test_lose_range_is_connected_to_runtime_sense():
    sense_source = read_source("AI/Sense.py")
    tree = ast.parse(sense_source, str(MOB_ROOT / "AI" / "Sense.py"))
    refresh_args = None
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "refresh_target":
            refresh_args = [arg.arg for arg in node.args.args]
            break
    assert refresh_args is not None
    assert refresh_args[:6] == ["self", "mob", "visionRange", "attackRange", "loseRange", "pursuitMemoryTime"]
    assert "effectiveLoseRange = max(float(visionRange), float(loseRange))" in sense_source
    assert 'self._lose_target(mob, "out_of_lose_range")' in sense_source
    assert "intellect.loseRange" in sense_source
    assert "self.targetInLoseRange = reason" not in sense_source


def main():
    test_intellect_ranges_drive_json_selector()
    test_warden_preserves_native_anger_target_chain()
    test_selector_lifecycle_restores_original_components()
    test_lose_range_is_connected_to_runtime_sense()
    print("intellect JSON targeting regression checks passed")


if __name__ == "__main__":
    main()
