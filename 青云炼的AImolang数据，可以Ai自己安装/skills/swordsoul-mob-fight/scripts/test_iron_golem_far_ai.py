# coding=utf-8
"""铁傀儡远距 AI 模拟射程校准回归检查。"""

import ast
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[4]
MOB_SCRIPT_ROOT = PROJECT_ROOT / "src" / "SwordSoul_NewERA_B" / "SwordSoulMobFightScripts"
AI_ROOT = MOB_SCRIPT_ROOT / "AI"
CORE_PATH = AI_ROOT / "Core.py"
SENSE_PATH = AI_ROOT / "Sense.py"
SKILL_PATH = AI_ROOT / "Skill.py"
IRON_GOLEM_PATH = MOB_SCRIPT_ROOT / "Entities" / "IronGolemMob.py"


def ReadAssignment(Tree, Name):
    for Node in Tree.body:
        if not isinstance(Node, ast.Assign):
            continue
        if any(isinstance(Target, ast.Name) and Target.id == Name for Target in Node.targets):
            return ast.literal_eval(Node.value)
    raise AssertionError("missing assignment: %s" % Name)


def ReadClassAssignments(PathValue, ClassName):
    Tree = ast.parse(PathValue.read_text(encoding="utf-8-sig"))
    ClassNode = next(
        Node for Node in Tree.body
        if isinstance(Node, ast.ClassDef) and Node.name == ClassName
    )
    Result = {}
    for Node in ClassNode.body:
        if not isinstance(Node, ast.Assign) or not isinstance(Node.targets[0], ast.Name):
            continue
        try:
            Result[Node.targets[0].id] = ast.literal_eval(Node.value)
        except (ValueError, TypeError):
            continue
    return Result


def ReadTopLevelNode(Tree, NodeType, Name):
    for Node in Tree.body:
        if isinstance(Node, NodeType) and Node.name == Name:
            return Node
    raise AssertionError("missing node: %s" % Name)


def BuildRangeHarness():
    SkillTree = ast.parse(SKILL_PATH.read_text(encoding="utf-8-sig"))
    ResolveNode = ReadTopLevelNode(SkillTree, ast.FunctionDef, "_resolve_skill_range_hint")
    Namespace = {"AI_SKILL_RANGE_HINTS": ReadAssignment(SkillTree, "AI_SKILL_RANGE_HINTS")}
    ResolveModule = ast.Module(body=[ResolveNode], type_ignores=[])
    ast.fix_missing_locations(ResolveModule)
    exec(compile(ResolveModule, str(SKILL_PATH), "exec"), Namespace)

    SenseTree = ast.parse(SENSE_PATH.read_text(encoding="utf-8-sig"))
    Namespace["STATE_RANGE_HINTS"] = ReadAssignment(SenseTree, "STATE_RANGE_HINTS")
    SafeFloatNode = ReadTopLevelNode(SenseTree, ast.FunctionDef, "_safe_float")
    ProfileNode = ReadTopLevelNode(SenseTree, ast.ClassDef, "SkillRangeProfile")
    ProfileModule = ast.Module(body=[SafeFloatNode, ProfileNode], type_ignores=[])
    ast.fix_missing_locations(ProfileModule)
    exec(compile(ProfileModule, str(SENSE_PATH), "exec"), Namespace)
    return Namespace


def AssertFarOpenerUsesEffectiveRange():
    Tree = ast.parse(CORE_PATH.read_text(encoding="utf-8-sig"))
    FunctionNode = next(
        Node for Node in Tree.body
        if isinstance(Node, ast.ClassDef) and Node.name == "MobAICore"
    )
    FarOpenerNode = next(
        Node for Node in FunctionNode.body
        if isinstance(Node, ast.FunctionDef) and Node.name == "_try_far_opener_decision"
    )
    EffectiveAssignment = next(
        Node for Node in FarOpenerNode.body
        if isinstance(Node, ast.Assign)
        and isinstance(Node.targets[0], ast.Name)
        and Node.targets[0].id == "effectiveOpeners"
    )
    Call = EffectiveAssignment.value
    assert isinstance(Call, ast.Call)
    assert isinstance(Call.func, ast.Attribute) and Call.func.attr == "filter"
    for VariableName in ("openerId", "skill"):
        Assignment = next(
            Node for Node in FarOpenerNode.body
            if isinstance(Node, ast.Assign)
            and isinstance(Node.targets[0], ast.Name)
            and Node.targets[0].id == VariableName
        )
        assert any(
            isinstance(Node, ast.Name) and Node.id == "effectiveOpeners"
            for Node in ast.walk(Assignment.value)
        ), VariableName


def Main():
    # Codex 2026-08-04: 以铁傀儡一段真实攻击和位移校准模拟射程，不通过禁用候选规避误判。
    IronConfig = ReadClassAssignments(IRON_GOLEM_PATH, "IronGolemMob")

    class FakeIronGolem(object):
        AISkillRangeHintOverrideMap = IronConfig["AISkillRangeHintOverrideMap"]

    Harness = BuildRangeHarness()
    ResolveHint = Harness["_resolve_skill_range_hint"]
    Hint = ResolveHint(FakeIronGolem(), "far_probe_attack")
    GenericHint = Harness["AI_SKILL_RANGE_HINTS"]["far_probe_attack"]
    GenericProfile = Harness["SkillRangeProfile"]("fight_attack_first")
    GenericProfile.apply_author_hint(GenericHint)
    GenericPredictedRange = GenericProfile.predicted_max_range(0.0, True)
    Profile = Harness["SkillRangeProfile"]("fight_attack_first")
    Profile.apply_author_hint(Hint)
    PredictedRange = Profile.predicted_max_range(0.0, True)
    SprintProfile = Harness["SkillRangeProfile"]("fight_attack_sprint")
    SprintProfile.apply_author_hint(Harness["STATE_RANGE_HINTS"]["fight_attack_sprint"])
    SprintPredictedRange = SprintProfile.predicted_max_range(0.0, True)

    assert "aiIntellectParams" not in IronConfig
    assert GenericHint["max_range"] == 6.8 and GenericHint["pre_hit_move"] == 2.6
    assert Hint["max_range"] == 3.0
    assert Hint["pre_hit_move"] == 0.10
    assert Hint["attack_window_move"] == 0.0
    assert Hint["first_hit_time"] == 0.63
    assert 10.6 <= GenericPredictedRange <= 10.8, GenericPredictedRange
    assert 3.5 <= PredictedRange <= 3.6, PredictedRange
    assert PredictedRange < 4.6
    assert SprintPredictedRange > 8.2, SprintPredictedRange
    CapabilityMap = ReadAssignment(ast.parse(CORE_PATH.read_text(encoding="utf-8-sig")), "_SKILL_CAPABILITY_MAP")
    assert "far_probe_attack" not in CapabilityMap
    assert "far_probe_budge_forward" not in CapabilityMap
    AssertFarOpenerUsesEffectiveRange()
    print(
        "iron golem far AI valid: generic=%.2f calibrated=%.2f sprint=%.2f"
        % (GenericPredictedRange, PredictedRange, SprintPredictedRange)
    )


if __name__ == "__main__":
    Main()
