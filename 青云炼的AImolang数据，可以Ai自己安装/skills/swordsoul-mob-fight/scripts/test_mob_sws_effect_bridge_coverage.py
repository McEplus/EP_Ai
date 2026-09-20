# coding=utf-8
"""SWS 公开特效、Mob 静态调用与客户端桥接的全量覆盖回归。"""

import ast
import copy
import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[4]
BEHAVIOR_ROOT = PROJECT_ROOT / "src" / "SwordSoul_NewERA_B"
RESOURCE_ROOT = PROJECT_ROOT / "src" / "SwordSoul_NewERA_R"
SWS_EFFECT_ROOT = BEHAVIOR_ROOT / "SwordSoulFightScripts" / "EffectSystem"
MOB_ROOT = BEHAVIOR_ROOT / "SwordSoulMobFightScripts"
MOB_RENDER_PATH = MOB_ROOT / "Render" / "MobRenderClient.py"

COMPONENT_PATHS = {
    "AttackEffectSystem": SWS_EFFECT_ROOT / "Fight.py",
    "DefenseEffectSystem": SWS_EFFECT_ROOT / "Fight.py",
    "SneakingEffectSystem": SWS_EFFECT_ROOT / "Fight.py",
    "SkillEffectSystem": SWS_EFFECT_ROOT / "Fight.py",
    "SkillPostEffectSystem": SWS_EFFECT_ROOT / "Screen.py",
    "CommonSoundSystem": SWS_EFFECT_ROOT / "Sound.py",
    "SkillSoundSystem": SWS_EFFECT_ROOT / "Sound.py",
}

# Codex 2026-08-05: 这些方法是组件生命周期或本地内部实现，不是 Mob 可调用的特效入口。
INTERNAL_PUBLIC_METHODS = {
    "AttackEffectSystem": {"UpdateEffectToEntity", "SetLightFire", "RefreshQuality"},
    "SneakingEffectSystem": {"SneakingRenderTick", "RefreshQuality"},
    "SkillEffectSystem": {"DimensionalSeverLightningLocal"},
    "SkillPostEffectSystem": {
        "InitPost", "OnRegisterPostConfig", "RegisterPostConfig", "UpdatePostState", "RefreshQuality"
    },
}


def ReadTree(PathValue):
    return ast.parse(PathValue.read_text(encoding="utf-8-sig"))


def FindClass(Tree, ClassName):
    return next(
        Node for Node in Tree.body
        if isinstance(Node, ast.ClassDef) and Node.name == ClassName
    )


def FindMethod(ClassNode, MethodName):
    return next(
        Node for Node in ClassNode.body
        if isinstance(Node, ast.FunctionDef) and Node.name == MethodName
    )


def StringConstants(Node):
    return {
        Child.value for Child in ast.walk(Node)
        if isinstance(Child, ast.Constant) and isinstance(Child.value, str)
    }


def ComponentMethods(ComponentName):
    ClassNode = FindClass(ReadTree(COMPONENT_PATHS[ComponentName]), ComponentName)
    return {
        Node.name for Node in ClassNode.body
        if isinstance(Node, ast.FunctionDef) and Node.name != "__init__"
    }


def PublicComponentMethods(ComponentName):
    return {
        MethodName for MethodName in ComponentMethods(ComponentName)
        if not MethodName.startswith("_")
    }


def ReadDirectRoutes(RenderClass):
    MethodNode = FindMethod(RenderClass, "_is_direct_sws_effect_method")
    for Node in ast.walk(MethodNode):
        if not isinstance(Node, ast.Assign):
            continue
        if any(isinstance(Target, ast.Name) and Target.id == "directMethods" for Target in Node.targets):
            return ast.literal_eval(Node.value)
    raise AssertionError("directMethods mapping missing")


def BuildBridgeRoutes():
    RenderClass = FindClass(ReadTree(MOB_RENDER_PATH), "MobFightRenderSystem")
    DirectRoutes = ReadDirectRoutes(RenderClass)
    RouteFunctions = {
        "AttackEffectSystem": ("_play_localized_attack_effect",),
        "DefenseEffectSystem": ("_play_localized_sws_effect", "_play_mob_defense_effect"),
        "SneakingEffectSystem": ("_play_localized_sneaking_effect",),
        "SkillEffectSystem": ("_play_localized_sws_effect", "_play_mob_skill_effect"),
        "SkillPostEffectSystem": ("_play_mob_skill_post_effect",),
        "CommonSoundSystem": ("_play_localized_sws_sound",),
        "SkillSoundSystem": ("_play_localized_sws_sound",),
    }
    Routes = {}
    for ComponentName, FunctionNames in RouteFunctions.items():
        ComponentRoutes = set()
        for FunctionName in FunctionNames:
            ComponentRoutes.update(StringConstants(FindMethod(RenderClass, FunctionName)))
        DirectComponentRoutes = DirectRoutes.get(ComponentName, ())
        if DirectComponentRoutes is None:
            ComponentRoutes.update(PublicComponentMethods(ComponentName))
        else:
            ComponentRoutes.update(DirectComponentRoutes)
        Routes[ComponentName] = ComponentRoutes
    return Routes


def AssertEveryPublicEffectIsRouted(Routes):
    RoutedCount = 0
    for ComponentName in COMPONENT_PATHS:
        ExternalMethods = PublicComponentMethods(ComponentName) - INTERNAL_PUBLIC_METHODS.get(ComponentName, set())
        MissingMethods = ExternalMethods - Routes[ComponentName]
        assert not MissingMethods, (ComponentName, sorted(MissingMethods))
        RoutedCount += len(ExternalMethods)
    return RoutedCount


def ExtractStaticMobUses():
    Uses = []
    ComponentNames = set(COMPONENT_PATHS)
    for PathValue in MOB_ROOT.rglob("*.py"):
        if "QingYunModLibs" in PathValue.parts or "Render" in PathValue.parts:
            continue
        Tree = ReadTree(PathValue)
        for Node in ast.walk(Tree):
            if not isinstance(Node, ast.Call):
                continue
            LiteralArgs = []
            for Argument in Node.args:
                try:
                    LiteralArgs.append(ast.literal_eval(Argument))
                except (ValueError, TypeError):
                    LiteralArgs.append(None)
            for Index in range(len(LiteralArgs) - 1):
                ComponentName = LiteralArgs[Index]
                MethodName = LiteralArgs[Index + 1]
                if not isinstance(ComponentName, str) or ComponentName not in ComponentNames:
                    continue
                if isinstance(MethodName, str):
                    Uses.append((ComponentName, MethodName, PathValue, Node.lineno))
    return Uses


def AssertStaticMobUsesAreDefinedAndRouted(Routes):
    Uses = ExtractStaticMobUses()
    assert Uses, "no static Mob SWS effect calls found"
    for ComponentName, MethodName, PathValue, LineNumber in Uses:
        assert MethodName in ComponentMethods(ComponentName), (
            "undefined", ComponentName, MethodName, str(PathValue), LineNumber
        )
        assert MethodName in Routes[ComponentName], (
            "unrouted", ComponentName, MethodName, str(PathValue), LineNumber
        )
    return len(Uses)


def AssertSingleSmokeEntrances():
    FightTree = ReadTree(COMPONENT_PATHS["AttackEffectSystem"])
    AttackClass = FindClass(FightTree, "AttackEffectSystem")
    Expected = {
        "SprintSmoke": ("_SprintSmokeEffect", "arris:sprint_smoke", "sprint_smoke.particle.json"),
        "DodgeSmoke": ("_DodgeSmokeEffect", "arris:dodge_smoke", "dodge_smoke.particle.json"),
    }
    for PublicMethod, (LocalMethod, ParticleName, FileName) in Expected.items():
        assert LocalMethod in StringConstants(FindMethod(AttackClass, PublicMethod))
        assert ParticleName in StringConstants(FindMethod(AttackClass, LocalMethod))
        ParticlePath = RESOURCE_ROOT / "particles" / FileName
        ParticleData = json.loads(ParticlePath.read_text(encoding="utf-8-sig"))
        Description = ParticleData["particle_effect"]["description"]
        Components = ParticleData["particle_effect"]["components"]
        assert Description["identifier"] == ParticleName
        assert (
            "minecraft:emitter_rate_manual" in Components
            or "minecraft:emitter_rate_instant" in Components
        )
    RenderStrings = StringConstants(FindClass(ReadTree(MOB_RENDER_PATH), "MobFightRenderSystem"))
    for PublicMethod, (LocalMethod, _, _) in Expected.items():
        assert PublicMethod in RenderStrings
        assert LocalMethod in RenderStrings


def AssertSmokeBridgeRuntime():
    RenderClass = FindClass(ReadTree(MOB_RENDER_PATH), "MobFightRenderSystem")
    HarnessClass = ast.ClassDef(
        name="SmokeBridgeHarness",
        bases=[ast.Name(id="object", ctx=ast.Load())],
        keywords=[],
        body=[
            copy.deepcopy(FindMethod(RenderClass, "_normalize_swordsoul_effect_args")),
            copy.deepcopy(FindMethod(RenderClass, "_play_localized_attack_effect")),
        ],
        decorator_list=[],
    )
    HarnessModule = ast.fix_missing_locations(ast.Module(body=[HarnessClass], type_ignores=[]))
    Namespace = {}
    exec(compile(HarnessModule, str(MOB_RENDER_PATH), "exec"), Namespace)
    Harness = Namespace["SmokeBridgeHarness"]()
    Calls = []
    Harness._call_sws_component_local = lambda *Args: Calls.append(Args) or True
    Harness._call_sws_public_effect_local = lambda *Args: Calls.append(Args) or None

    Args = Harness._normalize_swordsoul_effect_args(
        "AttackEffectSystem", "DodgeSmoke", ["stale-entity", (0, 0, 2)], "current-mob"
    )
    assert Args == ["current-mob", (0, 0, 2)]
    assert Harness._play_localized_attack_effect("DodgeSmoke", Args, "current-mob") is True
    assert Calls[-1] == (
        "AttackEffectSystem", "_DodgeSmokeEffect",
        ["current-mob", (0, 0, 2), (0, 0, 0)]
    )

    assert Harness._play_localized_attack_effect(
        "onDoomHit", ["stale-entity"], "current-mob"
    ) is True
    assert Calls[-1] == ("AttackEffectSystem", "onHit", ["current-mob"])


def AssertLocalDispatchIsConsumed():
    RenderClass = FindClass(ReadTree(MOB_RENDER_PATH), "MobFightRenderSystem")
    DispatchMethod = FindMethod(RenderClass, "_play_swordsoul_effect")
    ExplicitFalseChecks = [
        Node for Node in ast.walk(DispatchMethod)
        if isinstance(Node, ast.Compare)
        and any(isinstance(Operator, ast.IsNot) for Operator in Node.ops)
        and any(
            isinstance(Comparator, ast.Constant) and Comparator.value is False
            for Comparator in Node.comparators
        )
    ]
    assert len(ExplicitFalseChecks) >= 5, len(ExplicitFalseChecks)
    AttackRouteStrings = StringConstants(FindMethod(RenderClass, "_play_localized_attack_effect"))
    assert {"onHit", "onDoomHit"}.issubset(AttackRouteStrings)


def Main():
    # Codex 2026-08-05: 同时锁定资源、SWS 入口、Mob 路由与已消费语义，禁止以后再出现“有特效文件但调不起来”。
    Routes = BuildBridgeRoutes()
    RoutedCount = AssertEveryPublicEffectIsRouted(Routes)
    StaticUseCount = AssertStaticMobUsesAreDefinedAndRouted(Routes)
    AssertSingleSmokeEntrances()
    AssertSmokeBridgeRuntime()
    AssertLocalDispatchIsConsumed()
    print(
        "Mob SWS effect bridge coverage valid: routed_public=%d static_uses=%d"
        % (RoutedCount, StaticUseCount)
    )


if __name__ == "__main__":
    Main()
