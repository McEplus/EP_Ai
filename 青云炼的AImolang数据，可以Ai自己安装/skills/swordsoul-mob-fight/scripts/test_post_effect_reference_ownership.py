# coding=utf-8
"""共享后处理按实体和实例 token 持有的生命周期回归。"""

import ast
import copy
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[4]
SWS_ROOT = PROJECT_ROOT / "src" / "SwordSoul_NewERA_B" / "SwordSoulFightScripts"
SCREEN_PATH = SWS_ROOT / "EffectSystem" / "Screen.py"
ENGINE_PATH = SWS_ROOT / "QingYunModLibs" / "QyEngine" / "EngineClient.py"
MOB_ENGINE_PATH = (
    PROJECT_ROOT / "src" / "SwordSoul_NewERA_B" / "SwordSoulMobFightScripts"
    / "QingYunModLibs" / "QyEngine" / "EngineClient.py"
)


def ReadTree(PathValue):
    return ast.parse(PathValue.read_text(encoding="utf-8-sig"), filename=str(PathValue))


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


class FakeQuality(object):
    BlockedSources = set()

    @classmethod
    def AllowsPost(cls, PostName, SourceId=None):
        return SourceId not in cls.BlockedSources


class FakePostProcess(object):
    Calls = []

    @classmethod
    def SetEnableByName(cls, PostName, Enabled):
        cls.Calls.append((PostName, bool(Enabled)))


def BuildOwnershipHarness():
    SourceClass = FindClass(ReadTree(SCREEN_PATH), "SkillPostEffectSystem")
    Methods = [
        copy.deepcopy(FindMethod(SourceClass, Name))
        for Name in ("_NormalizePostOwnerToken", "_GetPostSourceMap", "UpdatePostState")
    ]
    HarnessClass = ast.ClassDef(
        name="OwnershipHarness",
        bases=[],
        keywords=[],
        body=Methods,
        decorator_list=[],
        type_params=[],
    )
    Module = ast.Module(body=[HarnessClass], type_ignores=[])
    ast.fix_missing_locations(Module)
    Namespace = {
        "Quality": FakeQuality,
        "PostProcessComp": FakePostProcess,
    }
    exec(compile(Module, str(SCREEN_PATH), "exec"), Namespace)
    Instance = Namespace["OwnershipHarness"]()
    Instance.PostStateMap = {}
    Instance._SetPostState = lambda Data: Instance.UpdatePostState(
        Data[0], Data[1], Data[2], Data[3] if len(Data) > 3 else None
    )
    return Instance


def AssertOverlappingOwnership():
    System = BuildOwnershipHarness()
    FakePostProcess.Calls = []
    FakeQuality.BlockedSources = set()

    System.UpdatePostState("player", "shared_post", True, "effect_a")
    System.UpdatePostState("player", "shared_post", True, "effect_b")
    System.UpdatePostState("player", "shared_post", False, "effect_a")
    assert FakePostProcess.Calls[-1] == ("shared_post", True)
    assert System.PostStateMap["shared_post"]["player"] == {"__instance__:effect_b": 1}

    System.UpdatePostState("player", "shared_post", False, "effect_b")
    assert FakePostProcess.Calls[-1] == ("shared_post", False)
    assert "player" not in System.PostStateMap["shared_post"]

    System.UpdatePostState("player_a", "cross_entity", True, "effect_a")
    System.UpdatePostState("player_b", "cross_entity", True, "effect_b")
    System.UpdatePostState("player_a", "cross_entity", False, "effect_a")
    assert FakePostProcess.Calls[-1] == ("cross_entity", True)
    System.UpdatePostState("player_b", "cross_entity", False, "effect_b")
    assert FakePostProcess.Calls[-1] == ("cross_entity", False)


def AssertIdempotentAndLegacyOwnership():
    System = BuildOwnershipHarness()
    FakePostProcess.Calls = []

    System.UpdatePostState("player", "idempotent", True, "same_effect")
    System.UpdatePostState("player", "idempotent", True, "same_effect")
    assert System.PostStateMap["idempotent"]["player"] == {"__instance__:same_effect": 1}
    System.UpdatePostState("player", "idempotent", False, "same_effect")
    assert FakePostProcess.Calls[-1] == ("idempotent", False)

    System.UpdatePostState("player", "legacy", True)
    System.UpdatePostState("player", "legacy", True)
    assert System.PostStateMap["legacy"]["player"] == {"__legacy__": 1}
    System.UpdatePostState("player", "legacy", False)
    assert FakePostProcess.Calls[-1] == ("legacy", False)
    assert "player" not in System.PostStateMap["legacy"]

    System.PostStateMap["hot_reload"] = ["player_a", "player_b"]
    Migrated = System._GetPostSourceMap("hot_reload")
    assert Migrated == {
        "player_a": {"__legacy__": 1},
        "player_b": {"__legacy__": 1},
    }
    System.PostStateMap["legacy_count_hot_reload"] = {
        "player": {"__legacy__": 7}
    }
    assert System._GetPostSourceMap("legacy_count_hot_reload") == {
        "player": {"__legacy__": 1}
    }


def AssertQualityFilteringKeepsOwnership():
    System = BuildOwnershipHarness()
    FakePostProcess.Calls = []
    FakeQuality.BlockedSources = {"remote"}
    System.UpdatePostState("remote", "quality_post", True, "remote_effect")
    assert FakePostProcess.Calls[-1] == ("quality_post", False)
    assert System.PostStateMap["quality_post"]["remote"] == {"__instance__:remote_effect": 1}
    FakeQuality.BlockedSources = set()
    System.UpdatePostState("local", "quality_post", True, "local_effect")
    assert FakePostProcess.Calls[-1] == ("quality_post", True)


def GetEffectClass(EnginePath):
    return next(
        Node for Node in ReadTree(EnginePath).body
        if isinstance(Node, ast.ClassDef)
        and any(isinstance(Item, ast.FunctionDef) and Item.name == "freeQyFrag" for Item in Node.body)
    )


def AssertEngineInstanceTokens():
    for EnginePath in (ENGINE_PATH, MOB_ENGINE_PATH):
        EffectClass = GetEffectClass(EnginePath)
        PlayMethod = FindMethod(EffectClass, "play")
        ReleaseMethod = FindMethod(EffectClass, "_ReleasePostState")
        DestroyMethod = FindMethod(EffectClass, "destroy")
        FreeMethod = FindMethod(EffectClass, "freeQyFrag")
        PlayCalls = [
            Node for Node in ast.walk(PlayMethod)
            if isinstance(Node, ast.Call) and isinstance(Node.func, ast.Attribute)
            and Node.func.attr == "_SetPostState"
        ]
        assert len(PlayCalls) == 1
        assert "DestroyStarted" in {
            Node.value for Node in ast.walk(PlayMethod)
            if isinstance(Node, ast.Constant) and isinstance(Node.value, str)
        }
        PlayValues = PlayCalls[0].args[0].elts
        assert len(PlayValues) == 4 and ast.literal_eval(PlayValues[2]) is True
        assert isinstance(PlayValues[3], ast.Call)
        assert PlayValues[3].func.attr == "_GetPostOwnerToken"

        ReleaseLists = [
            Node.args[0] for Node in ast.walk(ReleaseMethod)
            if isinstance(Node, ast.Call) and isinstance(Node.func, ast.Attribute)
            and Node.func.attr == "_SetPostState" and isinstance(Node.args[0], ast.List)
        ]
        assert sorted(len(Node.elts) for Node in ReleaseLists) == [3, 4]
        assert any(
            isinstance(Node, ast.Call) and isinstance(Node.func, ast.Attribute)
            and Node.func.attr == "_ReleasePostState"
            for Node in ast.walk(DestroyMethod)
        )
        assert any(
            isinstance(Node, ast.Call) and isinstance(Node.func, ast.Attribute)
            and Node.func.attr == "_ReleasePostState"
            for Node in ast.walk(FreeMethod)
        )
        InitMethod = FindMethod(EffectClass, "__init__")
        InitAttrs = {
            Node.attr for Node in ast.walk(InitMethod) if isinstance(Node, ast.Attribute)
        }
        assert {"PostStateActive", "PostOwnerToken", "DestroyStarted"} <= InitAttrs


def BuildEngineLifecycleHarness(System):
    EffectClass = GetEffectClass(ENGINE_PATH)
    Methods = [
        copy.deepcopy(FindMethod(EffectClass, Name))
        for Name in ("_GetPostOwnerToken", "_ReleasePostState", "destroy")
    ]
    HarnessClass = ast.ClassDef(
        name="EngineLifecycleHarness",
        bases=[],
        keywords=[],
        body=Methods,
        decorator_list=[],
        type_params=[],
    )
    Module = ast.Module(body=[HarnessClass], type_ignores=[])
    ast.fix_missing_locations(Module)
    VaryingMap = {"EngineClientPostMap": {"shared_post": set([101, 102])}}
    Namespace = {
        "DestroyTimer": lambda Timer: None,
        "GetComponent": lambda Name: System,
        "GetVaryingClient": lambda Name, defaultValue=None: VaryingMap.get(Name, defaultValue),
        "SetVaryingClient": lambda Name, Value: VaryingMap.__setitem__(Name, Value),
    }
    exec(compile(Module, str(ENGINE_PATH), "exec"), Namespace)
    return Namespace["EngineLifecycleHarness"], VaryingMap


def AssertDestroyReleasesBeforeTailCleanup():
    System = BuildOwnershipHarness()
    FakePostProcess.Calls = []
    FakeQuality.BlockedSources = set()
    EngineHarness, VaryingMap = BuildEngineLifecycleHarness(System)
    # 模拟热更前仍存活的旧 Qy 实例留下的 legacy 所有者。
    System.UpdatePostState("player", "shared_post", True)

    Effects = []
    for EffectId, Token in ((101, "effect_a"), (102, "effect_b")):
        Effect = EngineHarness()
        Effect.EffectId = EffectId
        Effect.PostOwnerToken = Token
        Effect.PostStateActive = True
        Effect.DestroyStarted = False
        Effect.postName = "shared_post"
        Effect.bindEntity = "player"
        Effect.QyPartPool = ["tail_particle"]
        Effect.playState = True
        Effect.healthTimer = "timer"
        Effect.freeQyFrag = lambda: None
        Effect.effectListen = lambda Event, Func: None
        Effects.append(Effect)
        System.UpdatePostState("player", "shared_post", True, Token)

    Effects[0].destroy()
    assert Effects[0].QyPartPool == ["tail_particle"]
    assert FakePostProcess.Calls[-1] == ("shared_post", True)
    assert System.PostStateMap["shared_post"]["player"] == {
        "__instance__:effect_b": 1,
        "__legacy__": 1,
    }
    Effects[0].destroy()
    assert FakePostProcess.Calls[-1] == ("shared_post", True)

    Effects[1].destroy()
    assert FakePostProcess.Calls[-1] == ("shared_post", False)
    assert "player" not in System.PostStateMap["shared_post"]
    assert "shared_post" not in VaryingMap["EngineClientPostMap"]

    LegacyEffect = EngineHarness()
    LegacyEffect.EffectId = 201
    LegacyEffect.postName = "legacy_post"
    LegacyEffect.bindEntity = "player"
    LegacyEffect.QyPartPool = ["tail_particle"]
    LegacyEffect.playState = True
    LegacyEffect.healthTimer = "timer"
    LegacyEffect.freeQyFrag = lambda: None
    LegacyEffect.effectListen = lambda Event, Func: None
    System.UpdatePostState("player", "legacy_post", True)
    VaryingMap["EngineClientPostMap"] = {}
    LegacyEffect.destroy()
    assert FakePostProcess.Calls[-1] == ("legacy_post", False)
    assert "player" not in System.PostStateMap["legacy_post"]


def Main():
    AssertOverlappingOwnership()
    AssertIdempotentAndLegacyOwnership()
    AssertQualityFilteringKeepsOwnership()
    AssertEngineInstanceTokens()
    AssertDestroyReleasesBeforeTailCleanup()
    print("post effect ownership valid: overlap=2 legacy=idempotent destroy_release=immediate")


if __name__ == "__main__":
    Main()
