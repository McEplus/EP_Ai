# coding=utf-8
"""全体人形生物闪避结束后不得落入默认立正姿态的系统回归。"""

import ast
import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[4]
MOB_ROOT = PROJECT_ROOT / "src" / "SwordSoul_NewERA_B" / "SwordSoulMobFightScripts"
RESOURCE_ROOT = PROJECT_ROOT / "src" / "SwordSoul_NewERA_R"
BASE_MOB_PATH = MOB_ROOT / "Entities" / "BaseMob.py"
QINGYUN_MOB_PATH = MOB_ROOT / "Entities" / "QingYunMob.py"
CONTROLLER_PATH = MOB_ROOT / "Combat" / "FightController.py"
EMPTY_STATE_PATH = MOB_ROOT / "Entities" / "FightState" / "UseEmptyState.py"
STATIC_RENDER_PATH = MOB_ROOT / "Render" / "StaticRenderConfig.py"
STATIC_REGISTRY_PATH = MOB_ROOT / "Render" / "StaticRenderRegistry.py"
FIGHT_NONE_CONTROLLER_PATH = RESOURCE_ROOT / "animation_controllers" / "mob" / "humanoid_fight_none.animation_controllers.json"
FIGHT_CONTROLLER_PATH = RESOURCE_ROOT / "animation_controllers" / "player" / "fight.animation_controllers.json"
FIGHT_ANIMATION_PATH = RESOURCE_ROOT / "animations" / "player" / "sword_soul" / "fight_all.animation.json"
PLAYER_GEOMETRY_PATH = RESOURCE_ROOT / "models" / "entity" / "player" / "PlayerBetter3D.geo.json"


DIRECTION_MAP = {
    "EmptyDodgeForwardPerfect": "forward",
    "EmptyDodgeBackPerfect": "back",
    "EmptyDodgeLeftPerfect": "left",
    "EmptyDodgeRightPerfect": "right",
}


def ReadTree(PathValue):
    return ast.parse(PathValue.read_text(encoding="utf-8-sig"))


def ReadClassNode(PathValue, ClassName):
    # Codex 2026-08-10: BaseMob 为类型检查保留同名占位类，测试必须读取最后一个运行时定义。
    return [
        Node for Node in ReadTree(PathValue).body
        if isinstance(Node, ast.ClassDef) and Node.name == ClassName
    ][-1]


def ReadMethod(PathValue, ClassName, MethodName):
    ClassNode = ReadClassNode(PathValue, ClassName)
    return next(
        Node for Node in ClassNode.body
        if isinstance(Node, ast.FunctionDef) and Node.name == MethodName
    )


def CalledAttributes(NodeValue):
    return {
        Node.func.attr for Node in ast.walk(NodeValue)
        if isinstance(Node, ast.Call) and isinstance(Node.func, ast.Attribute)
    }


def ReadSelfAssignment(MethodNode, AttributeName):
    for Node in ast.walk(MethodNode):
        if not isinstance(Node, ast.Assign) or len(Node.targets) != 1:
            continue
        Target = Node.targets[0]
        if (
            isinstance(Target, ast.Attribute)
            and isinstance(Target.value, ast.Name)
            and Target.value.id == "self"
            and Target.attr == AttributeName
        ):
            return ast.literal_eval(Node.value)
    raise AssertionError("missing self.%s" % AttributeName)


def ReadClassLiteralAssignment(ClassNode, AttributeName):
    for Node in ClassNode.body:
        if not isinstance(Node, ast.Assign) or len(Node.targets) != 1:
            continue
        Target = Node.targets[0]
        if isinstance(Target, ast.Name) and Target.id == AttributeName:
            return ast.literal_eval(Node.value)
    raise AssertionError("missing class assignment %s" % AttributeName)


def ReadClassUpdateMap(ClassNode, AttributeName):
    Result = {}
    for Node in ClassNode.body:
        if not isinstance(Node, ast.Expr) or not isinstance(Node.value, ast.Call):
            continue
        Call = Node.value
        if (
            isinstance(Call.func, ast.Attribute)
            and Call.func.attr == "update"
            and isinstance(Call.func.value, ast.Name)
            and Call.func.value.id == AttributeName
            and len(Call.args) == 1
        ):
            Result.update(ast.literal_eval(Call.args[0]))
    return Result


def BuildRenderHarness():
    BaseSync = ReadMethod(BASE_MOB_PATH, "SwordSoulMobEntity", "sync_fight_render_state")
    FightNoneSync = ReadMethod(BASE_MOB_PATH, "SwordSoulMobEntity", "sync_fight_none_render_state")
    ClassNode = ast.ClassDef(
        name="RenderHarness",
        bases=[ast.Name(id="object", ctx=ast.Load())],
        keywords=[],
        body=[BaseSync, FightNoneSync],
        decorator_list=[],
    )
    ModuleNode = ast.Module(body=[ClassNode], type_ignores=[])
    ast.fix_missing_locations(ModuleNode)

    class FakeMode(object):
        FIGHT = "fight"

    Namespace = {"MobCombatMode": FakeMode}
    exec(compile(ModuleNode, str(QINGYUN_MOB_PATH), "exec"), Namespace)
    return Namespace["RenderHarness"], FakeMode


def BuildHumanoidConfigHarness():
    BaseToDict = ReadMethod(STATIC_REGISTRY_PATH, "MobStaticRenderConfigBase", "to_dict")
    HumanoidToDict = ReadMethod(STATIC_RENDER_PATH, "HumanoidRenderConfig", "to_dict")
    EmptyAssignments = [
        ast.Assign(targets=[ast.Name(id=Name, ctx=ast.Store())], value=ast.Dict(keys=[], values=[]))
        for Name in (
            "geometry", "texture", "material", "animation", "animation_controller",
            "animation_controller_block", "script_animate", "render_controller", "molang",
        )
    ]
    BaseClass = ast.ClassDef(
        name="BaseConfig",
        bases=[ast.Name(id="object", ctx=ast.Load())],
        keywords=[],
        body=[
            ast.Assign(targets=[ast.Name(id="enabled", ctx=ast.Store())], value=ast.Constant(value=True)),
            *EmptyAssignments,
            ast.Assign(targets=[ast.Name(id="remove_animation_controller", ctx=ast.Store())], value=ast.List(elts=[], ctx=ast.Load())),
            ast.Assign(
                targets=[ast.Name(id="render_params", ctx=ast.Store())],
                value=ast.Dict(keys=[ast.Constant(value="rebuild")], values=[ast.Constant(value=True)]),
            ),
            BaseToDict,
        ],
        decorator_list=[],
    )
    HumanoidClass = ast.ClassDef(
        name="HumanoidConfigHarness",
        bases=[ast.Name(id="BaseConfig", ctx=ast.Load())],
        keywords=[],
        body=[
            ast.Assign(
                targets=[ast.Name(id="fight_none_animation_suffix", ctx=ast.Store())],
                value=ast.Constant(value=""),
            ),
            HumanoidToDict,
        ],
        decorator_list=[],
    )
    ModuleNode = ast.Module(body=[BaseClass, HumanoidClass], type_ignores=[])
    ast.fix_missing_locations(ModuleNode)
    Namespace = {"copy": __import__("copy"), "MobStaticRenderConfigBase": None}
    exec(compile(ModuleNode, str(STATIC_RENDER_PATH), "exec"), Namespace)
    Namespace["HumanoidConfigHarness"].to_dict.__globals__["MobStaticRenderConfigBase"] = Namespace["BaseConfig"]
    return Namespace["HumanoidConfigHarness"]


def Main():
    # Codex 2026-08-10: fight 始终描述完整战斗生命周期，fight_none 由 BaseMob 统一产生。
    BaseSync = ReadMethod(BASE_MOB_PATH, "SwordSoulMobEntity", "sync_fight_render_state")
    BaseFightNoneSync = ReadMethod(BASE_MOB_PATH, "SwordSoulMobEntity", "sync_fight_none_render_state")
    StateStart = ReadMethod(CONTROLLER_PATH, "MobFightController", "RunFightState")
    assert "sync_fight_none_render_state" in CalledAttributes(BaseSync)
    assert "sync_fight_none_render_state" in CalledAttributes(StateStart)
    assert "render_molang" in CalledAttributes(BaseFightNoneSync)
    QingYunClass = ReadClassNode(QINGYUN_MOB_PATH, "QingYunMob")
    assert not any(
        isinstance(Node, ast.FunctionDef) and Node.name == "sync_fight_none_render_state"
        for Node in QingYunClass.body
    )

    HarnessClass, FakeMode = BuildRenderHarness()
    Harness = HarnessClass()
    Values = []
    Harness.render_molang = lambda QueryId, Value: Values.append((QueryId, Value)) or True
    Harness.fight_controller = type("Controller", (object,), {"InFightState": False})()
    Harness.mode = FakeMode.FIGHT
    assert Harness.sync_fight_render_state()
    assert Values == [
        ("query.mod.fight", 1.0),
        ("query.mod.fight_none", 1.0),
    ]

    Values[:] = []
    Harness.fight_controller.InFightState = True
    assert Harness.sync_fight_render_state()
    assert Values == [
        ("query.mod.fight", 1.0),
        ("query.mod.fight_none", 0.0),
    ]

    Values[:] = []
    Harness.mode = "native"
    Harness.fight_controller.InFightState = False
    assert Harness.sync_fight_render_state()
    assert Values == [
        ("query.mod.fight", 0.0),
        ("query.mod.fight_none", 0.0),
    ]

    # Codex 2026-08-10: 共享人形控制器为所有 HumanoidRenderConfig 子类提供待机/行走托底。
    FightNoneControllers = json.loads(FIGHT_NONE_CONTROLLER_PATH.read_text(encoding="utf-8"))["animation_controllers"]
    FightNoneController = FightNoneControllers["controller.animation.mob_fight_none_humanoid"]
    assert "query.mod.fight" in FightNoneController["switch"]
    assert "query.mod.fight_none" in FightNoneController["switch"]
    RequiredFightNoneShortNames = {
        Name
        for CaseName in ("query.modified_move_speed <= 0.01", "query.modified_move_speed > 0.01")
        for Name in FightNoneController["case"][CaseName]["animations"]
    }
    assert RequiredFightNoneShortNames == {
        "fight_none_idle_empty", "fight_none_idle_empty_up",
        "fight_none_walk_empty", "fight_none_walk_empty_up",
    }

    ConfigClass = BuildHumanoidConfigHarness()
    StandardConfig = ConfigClass().to_dict()
    assert RequiredFightNoneShortNames <= set(StandardConfig["animation"])
    assert StandardConfig["animation_controller"]["c_mob_fight_none_humanoid"] == (
        "controller.animation.mob_fight_none_humanoid"
    )
    assert StandardConfig["script_animate"]["c_mob_fight_none_humanoid"] == ""
    assert StandardConfig["molang"]["query.mod.fight_none"] == 0.0
    YsmConfig = ConfigClass()
    YsmConfig.fight_none_animation_suffix = "_ysm"
    YsmAnimations = YsmConfig.to_dict()["animation"]
    assert all(Name.endswith("_ysm") for Name in YsmAnimations.values())

    RenderTree = ReadTree(STATIC_RENDER_PATH)
    RenderClasses = {Node.name: Node for Node in RenderTree.body if isinstance(Node, ast.ClassDef)}
    HumanoidChildren = {
        Name for Name, Node in RenderClasses.items()
        if any(isinstance(Base, ast.Name) and Base.id == "HumanoidRenderConfig" for Base in Node.bases)
    }
    assert {
        "QingYunRenderConfig", "HuskStaticRenderConfig", "DrownedStaticRenderConfig",
        "SkeletonStaticRenderConfig", "MaidRenderConfig",
    } <= HumanoidChildren
    assert all(
        not any(isinstance(Item, ast.FunctionDef) and Item.name == "to_dict" for Item in RenderClasses[Name].body)
        for Name in HumanoidChildren
    )

    # Codex 2026-08-10: 四向 Mob 完美闪避的状态、最后位移计时器和 actor 资源必须统一为 2.25 秒。
    StateTree = ReadTree(EMPTY_STATE_PATH)
    StateClasses = {
        Node.name: Node for Node in StateTree.body
        if isinstance(Node, ast.ClassDef) and Node.name in DIRECTION_MAP
    }
    HumanoidRender = ReadClassNode(STATIC_RENDER_PATH, "HumanoidRenderConfig")
    AnimationMap = ReadClassLiteralAssignment(HumanoidRender, "animation")
    FightController = json.loads(FIGHT_CONTROLLER_PATH.read_text(encoding="utf-8"))["animation_controllers"]["controller.animation.fight_all"]
    ActorAnimations = json.loads(FIGHT_ANIMATION_PATH.read_text(encoding="utf-8"))["animations"]
    GeometryData = json.loads(PLAYER_GEOMETRY_PATH.read_text(encoding="utf-8"))["minecraft:geometry"]
    Geometry = next(Item for Item in GeometryData if Item["description"]["identifier"] == "geometry.better_player_3d")
    GeometryBones = {Bone["name"] for Bone in Geometry["bones"]}

    assert set(StateClasses) == set(DIRECTION_MAP)
    for ClassName, Direction in DIRECTION_MAP.items():
        ClassNode = StateClasses[ClassName]
        InitMethod = next(Node for Node in ClassNode.body if isinstance(Node, ast.FunctionDef) and Node.name == "__init__")
        StartMethod = next(Node for Node in ClassNode.body if isinstance(Node, ast.FunctionDef) and Node.name == "onStart")
        StateAnimTime = ReadSelfAssignment(InitMethod, "StateAnimTime")
        AnimationMolang = ReadSelfAssignment(InitMethod, "AnimationMolang")
        TimerDelays = [
            float(Node.args[0].value)
            for Node in ast.walk(StartMethod)
            if isinstance(Node, ast.Call)
            and isinstance(Node.func, ast.Attribute)
            and Node.func.attr == "StateAnim_CreateTimer"
            and Node.args
            and isinstance(Node.args[0], ast.Constant)
            and isinstance(Node.args[0].value, (int, float))
        ]
        assert StateAnimTime == 2.25, ClassName
        assert max(TimerDelays) == StateAnimTime, ClassName

        CaseName = AnimationMolang.replace("query.mod.", "")
        ShortName = "fight_all_dodge_%s_perfect" % Direction
        FullName = "animation.fight.dodge_%s_perfect" % Direction
        assert FightController["case"][CaseName]["animations"] == [ShortName]
        assert AnimationMap[ShortName] == FullName
        Animation = ActorAnimations[FullName]
        assert Animation["animation_length"] == StateAnimTime
        assert Animation["loop"] == "hold_on_last_frame"
        assert set(Animation.get("bones", {})) <= GeometryBones

    print("shared humanoid dodge render-gap guard valid")


if __name__ == "__main__":
    Main()
