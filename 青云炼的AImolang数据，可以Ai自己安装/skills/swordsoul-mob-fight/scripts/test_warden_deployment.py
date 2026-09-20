# coding=utf-8
"""坚守者战斗资源、专属攻击时序、root_move 与原版门控的回归检查。"""

import ast
import copy
import importlib.util
import json
import re
import sys
import types
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[4]
RESOURCE_ROOT = PROJECT_ROOT / "src" / "SwordSoul_NewERA_R"
SCRIPT_ROOT = PROJECT_ROOT / "src" / "SwordSoul_NewERA_B" / "SwordSoulMobFightScripts"
BBMODEL_PATH = PROJECT_ROOT / "生物合集" / "坚守者" / "fight_warden.bbmodel"
ANIMATION_PATH = RESOURCE_ROOT / "animations" / "mob" / "wraden" / "fight_warden.animation.json"
CONTROLLER_PATH = RESOURCE_ROOT / "animation_controllers" / "mob" / "warden_fight.animation_controllers.json"
GEOMETRY_PATH = RESOURCE_ROOT / "models" / "entity" / "mob" / "warden.geo.json"
ENTITY_PATH = SCRIPT_ROOT / "Entities" / "WardenMob.py"
STATIC_PATH = SCRIPT_ROOT / "Render" / "StaticRenderConfig.py"
STATE_SOURCE_PATH = SCRIPT_ROOT / "Entities" / "FightState" / "UseEmptyState.py"


ANIMATION_SUFFIXES = {
    "walk", "attack_first", "attack_second", "attack_third", "attack_sprint",
    "sneaking", "attack_sneaking_1", "attack_sneaking_2", "try_defense",
    "attack_defense_1", "attack_defense_2", "common_defense", "perfect_defense",
    "attack_execute", "dodge_forward", "dodge_back", "dodge_right", "dodge_left",
    "hit_light", "hit_space", "hit_fall", "hit_heavy",
}
WARDEN_FIGHT_NONE_ANIMATIONS = [
    {"base_pose": "query.mod.fight && query.mod.fight_none"},
    {"move": "query.mod.fight && query.mod.fight_none"},
    {"bob": "query.mod.fight && query.mod.fight_none"},
    {"look_at_target": "query.mod.fight && query.mod.fight_none"},
]
SOURCE_LENGTHS = {
    "walk": 1.33333,
    "attack_first": 2.0,
    "attack_second": 1.83333,
    "attack_third": 2.75,
    "attack_sprint": 1.54167,
    "sneaking": 2.0,
    "attack_sneaking_1": 2.25,
    "attack_sneaking_2": 3.29167,
    "try_defense": 2.0,
    "attack_defense_1": 1.125,
    "attack_defense_2": 1.125,
    "common_defense": 1.0,
    "perfect_defense": 1.0,
    "attack_execute": 3.5,
    "dodge_forward": 1.25,
    "dodge_back": 1.25,
    "dodge_right": 1.25,
    "dodge_left": 1.25,
    "hit_light": 1.125,
    "hit_space": 1.0,
    "hit_fall": 1.0,
    "hit_heavy": 1.625,
}
LOGICAL_DURATIONS = {
    "attack_first": 1.8,
    "attack_second": 1.6,
    "attack_third": 2.5,
    "attack_sprint": 2.5,
    "attack_sneaking_1": 2.5,
    "attack_sneaking_2": 3.0,
    "attack_defense_1": 0.44,
    "attack_defense_2": 0.44,
    "common_defense": 0.8,
    "perfect_defense": 0.56,
    "attack_execute": 3.3,
    "dodge_forward": 1.0,
    "dodge_back": 1.0,
    "dodge_right": 1.0,
    "dodge_left": 1.0,
    "hit_light": 1.0,
    "hit_space": 1.0,
    "hit_fall": 1.0,
    "hit_heavy": 2.75,
}
CUSTOM_STATE_CONFIG = {
    "AttackFirst": {
        "suffix": "attack_first", "AttackTime": 0.8, "UnControlTime": 1.0,
        "StateKeepTime": 1.3, "StateAnimTime": 1.8,
        "hits": [0.7], "smoke": [],
    },
    "AttackSecond": {
        "suffix": "attack_second", "AttackTime": 0.8, "UnControlTime": 1.0,
        "StateKeepTime": 1.2, "StateAnimTime": 1.6,
        "hits": [0.65], "smoke": [],
    },
    "AttackThird": {
        "suffix": "attack_third", "AttackTime": 0.9, "UnControlTime": 1.2,
        "StateKeepTime": 2.0, "StateAnimTime": 2.5,
        "hits": [0.71], "smoke": [0.75],
    },
    "AttackSprint": {
        "suffix": "attack_sprint", "AttackTime": 0.6, "UnControlTime": 1.0,
        "StateKeepTime": 1.1, "StateAnimTime": 2.5,
        "hits": [0.46], "smoke": [1.3],
    },
    "AttackSneaking1": {
        "suffix": "attack_sneaking_1", "AttackTime": 1.1, "UnControlTime": 1.2,
        "StateKeepTime": 1.5, "StateAnimTime": 2.5,
        "hits": [0.46], "smoke": [2.0],
    },
    "AttackSneaking2": {
        "suffix": "attack_sneaking_2", "AttackTime": 2.3, "UnControlTime": 2.5,
        "StateKeepTime": 2.8, "StateAnimTime": 3.0,
        "hits": [0.3, 1.17, 2.13], "smoke": [1.2, 2.13],
    },
    "AttackExecute": {
        "suffix": "attack_execute", "AttackTime": 2.0, "UnControlTime": 2.2,
        "StateKeepTime": 2.5, "StateAnimTime": 3.3,
        "hits": [0.25, 1.88], "smoke": [],
    },
}
CUSTOM_DODGE_CONFIG = {
    "DodgeForward": {
        "suffix": "dodge_forward", "bone": "root", "rotation": (0, 0, 0),
    },
    "DodgeBack": {
        "suffix": "dodge_back", "bone": "root", "rotation": (0, 180, 0),
    },
    "DodgeLeft": {
        "suffix": "dodge_left", "bone": "", "rotation": (0, 90, 0),
    },
    "DodgeRight": {
        "suffix": "dodge_right", "bone": "", "rotation": (0, -90, 0),
    },
}
for Config in CUSTOM_DODGE_CONFIG.values():
    Config.update({
        "UnControlTime": 0.75, "StateKeepTime": 1.0, "StateAnimTime": 1.0,
        "smoke_start": 0.17, "smoke_end": 0.67, "smoke_duration": 0.50,
    })
CUSTOM_CLASS_BY_ANIMATION = dict(
    (Config["suffix"], ClassName) for ClassName, Config in CUSTOM_STATE_CONFIG.items()
)
CUSTOM_CLASS_BY_ANIMATION.update(
    (Config["suffix"], ClassName) for ClassName, Config in CUSTOM_DODGE_CONFIG.items()
)
STATE_CLASS_BY_ANIMATION = {
    "attack_first": "EmptyAttackFirst",
    "attack_second": "EmptyAttackSecond",
    "attack_third": "EmptyAttackThird",
    "attack_sprint": "EmptyAttackSprint",
    "attack_sneaking_1": "EmptyAttackSneaking1",
    "attack_sneaking_2": "EmptyAttackSneaking2",
    "attack_defense_1": "EmptyAttackDefense",
    "attack_defense_2": "EmptyAttackDefense",
    "common_defense": "EmptyCommonDefense",
    "perfect_defense": "EmptyPerfectDefense",
    "attack_execute": "EmptyAttackExecute",
    "dodge_forward": "EmptyDodgeForward",
    "dodge_back": "EmptyDodgeBack",
    "dodge_right": "EmptyDodgeRight",
    "dodge_left": "EmptyDodgeLeft",
    "hit_light": "EmptyHitLight",
    "hit_space": "EmptyHitSpace",
    "hit_fall": "EmptyHitSpace",
    "hit_heavy": "EmptyHitHeavy",
}
ALLOWED_STATES = {
    "fight_attack_first", "fight_attack_second", "fight_attack_third",
    "fight_attack_sprint", "fight_attack_execute", "fight_sneaking",
    "fight_attack_sneaking_1", "fight_attack_sneaking_2", "fight_attack_defense",
    "fight_try_defense", "fight_common_defense", "fight_perfect_defense",
    "fight_dodge_forward", "fight_dodge_back", "fight_dodge_left", "fight_dodge_right",
    "fight_budge_forward", "fight_budge_back", "fight_budge_left", "fight_budge_right",
    "fight_hit_light", "fight_hit_space", "fight_hit_heavy",
}


def ReadJson(PathValue):
    return json.loads(PathValue.read_text(encoding="utf-8"))


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
    return Result, ClassNode


def ReadMethod(ClassNode, MethodName):
    return next(
        Node for Node in ClassNode.body
        if isinstance(Node, ast.FunctionDef) and Node.name == MethodName
    )


def ReadSelfAssignments(PathValue, ClassName):
    _, ClassNode = ReadClassAssignments(PathValue, ClassName)
    InitNode = ReadMethod(ClassNode, "__init__")
    Result = {}
    for Node in InitNode.body:
        if not isinstance(Node, ast.Assign):
            continue
        Target = Node.targets[0]
        if not (
            isinstance(Target, ast.Attribute)
            and isinstance(Target.value, ast.Name)
            and Target.value.id == "self"
        ):
            continue
        try:
            Result[Target.attr] = ast.literal_eval(Node.value)
        except (ValueError, TypeError):
            continue
    return Result, ClassNode


def IsAttributeChain(Node, Parts):
    for Part in reversed(Parts[1:]):
        if not isinstance(Node, ast.Attribute) or Node.attr != Part:
            return False
        Node = Node.value
    return isinstance(Node, ast.Name) and Node.id == Parts[0]


def ReadAttackAndSmokeDelays(ClassNode):
    Hits = []
    Smoke = []
    for Node in ast.walk(ReadMethod(ClassNode, "onStart")):
        if not isinstance(Node, ast.Call):
            continue
        if IsAttributeChain(Node.func, ("self", "StateAnim_CreateTimer")) and len(Node.args) >= 2:
            if IsAttributeChain(Node.args[1], ("self", "PlayerRootController", "CreateAttack")):
                Hits.append(float(ast.literal_eval(Node.args[0])))
        if IsAttributeChain(Node.func, ("self", "ScheduleSwordSoulEffect")) and len(Node.args) >= 3:
            if ast.literal_eval(Node.args[2]) == "DirtSmoke":
                Smoke.append(float(ast.literal_eval(Node.args[0])))
    return sorted(Hits), sorted(Smoke)


def ReadDodgeSmokeWindow(ClassNode):
    MethodNode = ReadMethod(ClassNode, "ScheduleSWSRecentMovementEffects")
    Calls = [
        Node for Node in ast.walk(MethodNode)
        if isinstance(Node, ast.Call)
        and IsAttributeChain(Node.func, ("self", "ScheduleSwordSoulEffect"))
    ]
    assert len(Calls) == 1
    CallNode = Calls[0]
    assert ast.literal_eval(CallNode.args[1]) == "AttackEffectSystem"
    assert ast.literal_eval(CallNode.args[2]) == "DodgeDirtSmoke"
    EffectArgs = CallNode.args[3]
    assert isinstance(EffectArgs, ast.List) and len(EffectArgs.elts) == 5
    StartTime = float(ast.literal_eval(CallNode.args[0]))
    BoneName = ast.literal_eval(EffectArgs.elts[1])
    Rotation = tuple(ast.literal_eval(EffectArgs.elts[3]))
    Duration = float(ast.literal_eval(EffectArgs.elts[4]))
    return StartTime, StartTime + Duration, Duration, BoneName, Rotation


def ReadMotionSchedule(ClassNode):
    Schedule = []
    for Node in ast.walk(ReadMethod(ClassNode, "onStart")):
        if not isinstance(Node, ast.Call):
            continue
        if isinstance(Node.func, ast.Name) and Node.func.id == "SetMoveMotion":
            Delay = 0.0
            DirectionNode = Node.args[0]
            PowerNode = Node.args[1]
        elif (
            IsAttributeChain(Node.func, ("self", "StateAnim_CreateTimer"))
            and len(Node.args) >= 5
            and isinstance(Node.args[1], ast.Name)
            and Node.args[1].id == "SetMoveMotion"
        ):
            Delay = float(ast.literal_eval(Node.args[0]))
            DirectionNode = Node.args[3]
            PowerNode = Node.args[4]
        else:
            continue
        assert isinstance(PowerNode, ast.BinOp) and isinstance(PowerNode.op, ast.Mult)
        Direction = tuple(float(Value) for Value in ast.literal_eval(DirectionNode))
        Power = float(ast.literal_eval(PowerNode.left))
        Schedule.append((Delay, Direction, Power))
    return sorted(Schedule)


def ReadRootMoveNet(BBAnimation):
    RootAnimator = next(
        Animator for Animator in BBAnimation["animators"].values()
        if Animator.get("name") == "root_move"
    )
    PositionFrames = sorted(
        (Frame for Frame in RootAnimator["keyframes"] if Frame.get("channel") == "position"),
        key=lambda Frame: float(Frame["time"]),
    )
    assert PositionFrames

    def Point(Frame):
        Data = Frame["data_points"][-1]
        return tuple(float(Data[Axis]) for Axis in ("x", "y", "z"))

    First = Point(PositionFrames[0])
    Last = Point(PositionFrames[-1])
    Delta = tuple(Last[Index] - First[Index] for Index in range(3))
    return (Delta[0] * 0.00527, Delta[1] * 0.00527, -Delta[2] * 0.00527)


def ReadStateAnimTime(ClassName):
    Tree = ast.parse(STATE_SOURCE_PATH.read_text(encoding="utf-8-sig"))
    ClassNode = next(
        Node for Node in Tree.body
        if isinstance(Node, ast.ClassDef) and Node.name == ClassName
    )
    InitNode = next(
        Node for Node in ClassNode.body
        if isinstance(Node, ast.FunctionDef) and Node.name == "__init__"
    )
    for Node in InitNode.body:
        if not isinstance(Node, ast.Assign):
            continue
        Target = Node.targets[0]
        if (
            isinstance(Target, ast.Attribute)
            and isinstance(Target.value, ast.Name)
            and Target.value.id == "self"
            and Target.attr == "StateAnimTime"
        ):
            return float(ast.literal_eval(Node.value))
    raise AssertionError("missing StateAnimTime: " + ClassName)


def AssertAnimationNamespaceAndTiming():
    Exported = ReadJson(ANIMATION_PATH)["animations"]
    BBModel = ReadJson(BBMODEL_PATH)
    BBAnimations = dict((Item["name"], Item) for Item in BBModel["animations"])
    ExpectedNames = set("animation.fight_warden." + Name for Name in ANIMATION_SUFFIXES)
    assert set(Exported) == ExpectedNames
    assert set(BBAnimations) == ExpectedNames
    assert "arris_warden" not in ANIMATION_PATH.read_text(encoding="utf-8")
    assert "arris_warden" not in BBMODEL_PATH.read_text(encoding="utf-8")
    for Name in ExpectedNames:
        assert abs(float(Exported[Name]["animation_length"]) - float(BBAnimations[Name]["length"])) < 0.0001
    for Suffix, SourceLength in SOURCE_LENGTHS.items():
        Name = "animation.fight_warden." + Suffix
        assert abs(float(BBAnimations[Name]["length"]) - SourceLength) < 0.00001
    for Suffix, LogicalDuration in LOGICAL_DURATIONS.items():
        if Suffix in CUSTOM_CLASS_BY_ANIMATION:
            Assignments, _ = ReadSelfAssignments(ENTITY_PATH, CUSTOM_CLASS_BY_ANIMATION[Suffix])
            assert float(Assignments["StateAnimTime"]) == LogicalDuration
        else:
            assert ReadStateAnimTime(STATE_CLASS_BY_ANIMATION[Suffix]) == LogicalDuration
        Name = "animation.fight_warden." + Suffix
        ExportExpression = Exported[Name].get("anim_time_update", "")
        BBExpression = BBAnimations[Name].get("anim_time_update", "")
        assert ExportExpression == BBExpression
        Match = re.fullmatch(r"query\.anim_time \+ query\.delta_time \* ([0-9.]+)", ExportExpression)
        assert Match, (Suffix, ExportExpression)
        Scale = float(Match.group(1))
        SourceDuration = float(Exported[Name]["animation_length"])
        assert abs(SourceDuration / Scale - LogicalDuration) < 0.0001, Suffix
    for Suffix in ("walk", "sneaking", "try_defense"):
        Name = "animation.fight_warden." + Suffix
        assert not Exported[Name].get("anim_time_update")
        assert not BBAnimations[Name].get("anim_time_update")
    return len(Exported), len(LOGICAL_DURATIONS)


def AssertAttackTimingsAndRootMotion():
    BBAnimations = dict(
        (Item["name"], Item) for Item in ReadJson(BBMODEL_PATH)["animations"]
    )
    ExpectedPeakPower = {
        "AttackFirst": 0.3283,
        "AttackSecond": 0.5715,
        "AttackThird": 0.2260,
        "AttackSprint": 2.0623,
        "AttackSneaking1": 0.0537,
        "AttackSneaking2": 1.8425,
        "AttackExecute": 0.9619,
    }
    SegmentCount = 0
    for ClassName, Config in CUSTOM_STATE_CONFIG.items():
        Assignments, ClassNode = ReadSelfAssignments(ENTITY_PATH, ClassName)
        for FieldName in ("AttackTime", "UnControlTime", "StateKeepTime", "StateAnimTime"):
            assert float(Assignments[FieldName]) == Config[FieldName], (ClassName, FieldName)
        assert Config["AttackTime"] <= Config["UnControlTime"]
        assert Config["UnControlTime"] <= Config["StateKeepTime"]
        assert Config["StateKeepTime"] <= Config["StateAnimTime"]

        Hits, Smoke = ReadAttackAndSmokeDelays(ClassNode)
        assert Hits == Config["hits"], (ClassName, Hits)
        assert Smoke == Config["smoke"], (ClassName, Smoke)
        assert all(Delay <= Config["AttackTime"] for Delay in Hits)
        assert all(Delay <= Config["StateAnimTime"] for Delay in Smoke)

        Schedule = ReadMotionSchedule(ClassNode)
        assert Schedule[0][0] == 0.0
        assert Schedule[-1] == (Config["StateAnimTime"], (0.0, 0.0, 0.0), 0.0)
        assert all(Left[0] < Right[0] for Left, Right in zip(Schedule, Schedule[1:]))
        assert all(Right[0] - Left[0] >= 0.08 for Left, Right in zip(Schedule, Schedule[1:]))
        assert all(Power >= 0.0 for _, _, Power in Schedule)
        for _, Direction, Power in Schedule:
            LengthSquared = sum(Value * Value for Value in Direction)
            if Power > 0.0:
                assert abs(LengthSquared - 1.0) < 0.003, (ClassName, Direction)
        assert max(Power for _, _, Power in Schedule) == ExpectedPeakPower[ClassName]

        Integrated = [0.0, 0.0, 0.0]
        for Current, Following in zip(Schedule, Schedule[1:]):
            Delay, Direction, Power = Current
            DeltaTime = Following[0] - Delay
            for Axis in range(3):
                Integrated[Axis] += Direction[Axis] * Power * DeltaTime
        AnimationName = "animation.fight_warden." + Config["suffix"]
        ExpectedNet = ReadRootMoveNet(BBAnimations[AnimationName])
        for Axis in range(3):
            assert abs(Integrated[Axis] - ExpectedNet[Axis]) < 0.001, (
                ClassName, tuple(Integrated), ExpectedNet,
            )
        SegmentCount += len(Schedule)
    return len(CUSTOM_STATE_CONFIG), SegmentCount


def AssertDodgeTimingsAndSmoke():
    for ClassName, Config in CUSTOM_DODGE_CONFIG.items():
        Assignments, ClassNode = ReadSelfAssignments(ENTITY_PATH, ClassName)
        for FieldName in ("UnControlTime", "StateKeepTime", "StateAnimTime"):
            assert float(Assignments[FieldName]) == Config[FieldName], (ClassName, FieldName)
        assert Config["UnControlTime"] <= Config["StateKeepTime"] <= Config["StateAnimTime"]
        StartTime, EndTime, Duration, BoneName, Rotation = ReadDodgeSmokeWindow(ClassNode)
        assert StartTime == Config["smoke_start"], ClassName
        assert abs(EndTime - Config["smoke_end"]) < 0.000001, ClassName
        assert Duration == Config["smoke_duration"], ClassName
        assert BoneName == Config["bone"], ClassName
        assert Rotation == Config["rotation"], ClassName
    return len(CUSTOM_DODGE_CONFIG)


def AssertGeometryAndBoneResolution():
    Geometry = ReadJson(GEOMETRY_PATH)["minecraft:geometry"][0]
    Bones = Geometry["bones"]
    BoneMap = dict((Bone["name"], Bone) for Bone in Bones)
    assert len(BoneMap) == len(Bones)
    assert Geometry["description"]["identifier"] == "geometry.fight_warden"
    assert BoneMap["root"].get("parent") is None
    assert BoneMap["root_move"].get("parent") is None
    assert all(Bone.get("parent") != "root_move" for Bone in Bones)
    for Bone in Bones:
        Parent = Bone.get("parent")
        assert not Parent or Parent in BoneMap, (Bone["name"], Parent)
    for BoneName in BoneMap:
        Seen = set()
        CurrentName = BoneName
        while BoneMap[CurrentName].get("parent"):
            assert CurrentName not in Seen, "geometry parent cycle: " + BoneName
            Seen.add(CurrentName)
            CurrentName = BoneMap[CurrentName]["parent"]
    for BoneName in (
        "body", "waist", "waist2", "head", "nose", "right_ribcage", "left_ribcage",
        "right_tendril", "left_tendril", "right_arm", "right_arm2", "right_arm3",
        "left_arm", "left_arm2", "left_arm3", "right_leg", "right_leg2",
        "left_leg", "left_leg2",
    ):
        assert BoneName in BoneMap, BoneName
    UsedBones = set()
    for Animation in ReadJson(ANIMATION_PATH)["animations"].values():
        UsedBones.update((Animation.get("bones") or {}).keys())
    assert UsedBones <= set(BoneMap), sorted(UsedBones - set(BoneMap))
    return len(Bones), len(UsedBones)


def AssertControllerAndRenderBindings():
    Controller = ReadJson(CONTROLLER_PATH)["animation_controllers"]["controller.animation.fight_warden"]
    assert Controller["switch"] == "query.mod.{&}"
    assert Controller["case"]["default"]["animations"] == WARDEN_FIGHT_NONE_ANIMATIONS
    Refs = set()
    ExpectedBlend = {"0.05": 0.7, "0.1": 0.3, "0.15": 0.1, "0.2": 0.0}
    for CaseName, CaseData in Controller["case"].items():
        assert CaseData.get("blend_transition") == ExpectedBlend, CaseName
        assert CaseData.get("blend_via_shortest_path") is True, CaseName
        for Ref in CaseData.get("animations", []):
            Refs.add(next(iter(Ref)) if isinstance(Ref, dict) else Ref)
    ExpectedRefs = set("warden_" + Name for Name in ANIMATION_SUFFIXES - {"walk"})
    ExpectedRefs.update({"base_pose", "move", "bob", "look_at_target"})
    assert Refs == ExpectedRefs, sorted(ExpectedRefs - Refs)

    Assignments, _ = ReadClassAssignments(STATIC_PATH, "WardenStaticRenderConfig")
    assert Assignments["geometry"] == {"default": "geometry.fight_warden"}
    AnimationMap = Assignments["animation"]
    assert "warden_walk" not in AnimationMap
    for Suffix in ANIMATION_SUFFIXES - {"walk"}:
        assert AnimationMap["warden_" + Suffix] == "animation.fight_warden." + Suffix
    assert Assignments["animation_controller"]["c_warden_fight_controller"] == "controller.animation.fight_warden"
    assert all(Key.startswith("c_") for Key in Assignments["animation_controller"])
    assert set(Assignments["remove_animation_controller"]) == {
        "controller__shiver_controller", "controller__sniff_controller",
        "controller__roar_controller", "controller__melee_attack_controller",
        "controller__sonic_boom_controller",
    }
    ExpectedScripts = {
        "base_pose": "!query.mod.fight",
        "move": "!(query.is_emerging || query.is_digging) && !query.mod.fight",
        "c_shiver_controller": "!query.mod.fight",
        "bob": "!query.mod.fight",
        "emerge": "query.is_emerging && !query.mod.fight",
        "c_sniff_controller": "!query.mod.fight",
        "dig": "query.is_digging && !query.mod.fight",
        "c_roar_controller": "!query.mod.fight",
        "look_at_target": "!(query.is_emerging || query.is_digging) && !query.mod.fight",
        "c_melee_attack_controller": "!query.mod.fight",
        "swimming": "query.swim_amount > 0.0 && !query.mod.fight",
        "c_sonic_boom_controller": "!query.mod.fight",
        "c_warden_fight_controller": "",
    }
    assert Assignments["script_animate"] == ExpectedScripts
    assert Assignments["molang"]["query.mod.fight_none"] == 0.0
    return len(Controller["case"]), len(Refs)


def AssertNoCustomWardenWalkController():
    Controller = ReadJson(CONTROLLER_PATH)["animation_controllers"]["controller.animation.fight_warden"]
    assert Controller["case"]["default"]["animations"] == WARDEN_FIGHT_NONE_ANIMATIONS
    ControllerRefs = set()
    for CaseData in Controller["case"].values():
        for Ref in CaseData.get("animations", []):
            ControllerRefs.add(next(iter(Ref)) if isinstance(Ref, dict) else Ref)
    assert "warden_walk" not in ControllerRefs
    ExpectedRefs = set("warden_" + Name for Name in ANIMATION_SUFFIXES - {"walk"})
    ExpectedRefs.update({"base_pose", "move", "bob", "look_at_target"})
    assert ControllerRefs == ExpectedRefs

    Assignments, _ = ReadClassAssignments(STATIC_PATH, "WardenStaticRenderConfig")
    assert "warden_walk" not in Assignments["animation"]
    assert Assignments["animation_controller"]["c_warden_fight_controller"] == "controller.animation.fight_warden"
    assert Assignments["script_animate"]["c_warden_fight_controller"] == ""
    assert Assignments["molang"]["query.mod.fight_none"] == 0.0
    return len(ControllerRefs)


def AssertEntityDeployment():
    Source = ENTITY_PATH.read_text(encoding="utf-8-sig")
    Assignments, ClassNode = ReadClassAssignments(ENTITY_PATH, "WardenMob")
    assert Assignments["aiIntellect"] == "high"
    assert Assignments["IntellectJsonTargetSelectorEnabled"] is False
    assert Assignments["IntellectJsonTargetSelectorTemplate"] is None
    assert Assignments["IntellectJsonTargetSupportComponentMap"] == {}
    assert Assignments["ActiveTargetHoldsFightMode"] is False
    assert Assignments["PassiveSoftFightHoldEnabled"] is False
    assert Assignments["ExitFightModeOnStateNone"] is True
    assert Assignments["common_attack_sort_map"] == {"empty": [1, 2, 3]}
    assert set(Assignments["FightReactionFallbackMap"].values()) <= {
        "fight_hit_light", "fight_dodge_forward", "fight_dodge_back",
        "fight_dodge_left", "fight_dodge_right",
    }
    assert set(Assignments["NativeControlComponentMap"]) == {
        "minecraft:movement", "minecraft:navigation.walk", "minecraft:movement.basic",
        "minecraft:behavior.float", "minecraft:behavior.dig", "minecraft:behavior.roar",
        "minecraft:behavior.investigate_suspicious_location", "minecraft:behavior.sniff",
        "minecraft:behavior.random_stroll", "minecraft:behavior.random_look_around",
    }
    assert set(Assignments["NativeMeleeAttackComponentMap"]) == {
        "minecraft:attack", "minecraft:behavior.sonic_boom", "minecraft:behavior.melee_box_attack",
    }
    CombatModeMethod = next(
        Node for Node in ClassNode.body
        if isinstance(Node, ast.FunctionDef) and Node.name == "on_combat_mode_changed"
    )
    CombatModeSource = ast.get_source_segment(Source, CombatModeMethod)
    assert "set_native_control_enabled" in CombatModeSource
    assert "set_native_melee_attack_enabled" in CombatModeSource
    BaseSource = (SCRIPT_ROOT / "Entities" / "BaseMob.py").read_text(encoding="utf-8-sig")
    assert "self._active_target_holds_fight_mode()" in BaseSource
    assert 'new_state_id != "fight_none"' in BaseSource
    assert "return self.set_soft_switch(False)" in BaseSource
    BoundStates = set(re.findall(r'@BindMobState\(WARDEN_ENTITY_TYPE, "([^"]+)"\)', Source))
    assert BoundStates == ALLOWED_STATES, sorted(ALLOWED_STATES - BoundStates)
    assert not [Node for Node in ClassNode.body if isinstance(Node, ast.ClassDef)]
    for Node in ast.parse(Source).body:
        if not isinstance(Node, ast.ClassDef) or Node.name == "WardenMob":
            continue
        Methods = [Item.name for Item in Node.body if isinstance(Item, ast.FunctionDef)]
        if Node.name in CUSTOM_STATE_CONFIG:
            assert Methods == ["__init__", "onStart"], (Node.name, Methods)
        elif Node.name in CUSTOM_DODGE_CONFIG:
            assert Methods == ["__init__", "ScheduleSWSRecentMovementEffects"], (Node.name, Methods)
        else:
            assert Methods == ["__init__"], (Node.name, Methods)
    assert "comp.GetComponents()" in Source
    assert "self.mode == MobCombatMode.FIGHT" in Source
    assert 'cause == "sonic_boom"' in Source
    assert "self.enter_fight_mode()" in Source
    assert "return SwordSoulMobEntity.sync_fight_render_state(self)" in Source
    InitSource = (SCRIPT_ROOT / "Entities" / "__init__.py").read_text(encoding="utf-8-sig")
    assert "from . import WardenMob" in InitSource
    return len(BoundStates)


def AssertRuntimeComponentAndDamageTransitions():
    # Codex 2026-08-05: 用最小引擎桩执行真实 WardenMob 方法，覆盖组件恢复、涌出门和伤害竞态。
    sys.dont_write_bytecode = True
    RuntimeRoot = "warden_deployment_runtime"
    for Name in (
        RuntimeRoot, RuntimeRoot + ".Entities", RuntimeRoot + ".QingYunModLibs",
        RuntimeRoot + ".Core", RuntimeRoot + ".Combat", "FightState",
    ):
        Module = types.ModuleType(Name)
        Module.__path__ = []
        sys.modules[Name] = Module

    EmptyModule = types.ModuleType("FightState.UseEmptyState")
    EmptyNames = {
        "EmptyAttackFirst", "EmptyAttackSecond", "EmptyAttackThird", "EmptyAttackSprint",
        "EmptyAttackExecute", "EmptySneaking", "EmptyAttackSneaking1", "EmptyAttackSneaking2",
        "EmptyAttackDefense", "EmptyTryDefense", "EmptyCommonDefense", "EmptyPerfectDefense",
        "EmptyDodgeForward", "EmptyDodgeBack", "EmptyDodgeLeft", "EmptyDodgeRight",
        "EmptyBudgeForward", "EmptyBudgeBack", "EmptyBudgeLeft", "EmptyBudgeRight",
        "EmptyHitLight", "EmptyHitSpace", "EmptyHitHeavy",
    }
    for Name in EmptyNames:
        setattr(EmptyModule, Name, type(Name, (object,), {"__init__": lambda self: None}))
    EmptyModule.__all__ = sorted(EmptyNames)
    sys.modules["FightState.UseEmptyState"] = EmptyModule

    class FakeFightController(object):
        def __init__(self):
            self.calls = []
            self.InFightState = False

        def set_state(self, StateId, Request, Force):
            self.calls.append((StateId, Request, Force))
            return True

    class FakeBase(object):
        def __init__(self, EntityId):
            self.entityId = EntityId
            self.mode = "native"
            self.soft_enabled = False
            self.hard_enabled = True
            self.fight_controller = FakeFightController()
            self.render_values = {}

        def register_states(self):
            return True

        def get_all_fight_states(self):
            return {}

        def get_native_control_component_map(self):
            return self.NativeControlComponentMap

        def get_native_melee_attack_component_map(self):
            return self.NativeMeleeAttackComponentMap

        def remove_actor_component(self, ComponentName):
            return FakeServerComp.CreateEntityEvent(self.entityId).RemoveActorComponent(ComponentName)

        def add_actor_component(self, ComponentName, ComponentData=None):
            return FakeServerComp.CreateEntityEvent(self.entityId).AddActorComponent(ComponentName, ComponentData)

        def set_soft_switch(self, Enabled):
            self.soft_enabled = bool(Enabled) and self.hard_enabled
            self.mode = "fight" if self.soft_enabled else "native"
            return True

        def enter_fight_mode(self):
            if not self.hard_enabled:
                return False
            return self.set_soft_switch(True)

        def render_molang(self, Name, Value):
            self.render_values[Name] = Value
            return True

        def sync_fight_none_render_state(self):
            Enabled = (
                self.mode == "fight"
                and self.fight_controller
                and not self.fight_controller.InFightState
            )
            return self.render_molang("query.mod.fight_none", 1.0 if Enabled else 0.0)

        def sync_fight_render_state(self):
            self.render_molang("query.mod.fight", 1.0 if self.mode == "fight" else 0.0)
            self.sync_fight_none_render_state()
            return True

    BaseModule = types.ModuleType(RuntimeRoot + ".Entities.BaseMob")
    BaseModule.SwordSoulMobEntity = FakeBase
    sys.modules[BaseModule.__name__] = BaseModule

    class FakeEventComponent(object):
        def __init__(self, Components):
            self.components = copy.deepcopy(Components)
            self.defer_add = False

        def GetComponents(self):
            return copy.deepcopy(self.components)

        def RemoveActorComponent(self, Name):
            self.components.pop(Name, None)
            return True

        def AddActorComponent(self, Name, Data):
            if not self.defer_add:
                self.components[Name] = copy.deepcopy(Data)
            return True

    class FakeServerComp(object):
        event = None

        @classmethod
        def CreateEntityEvent(cls, EntityId):
            return cls.event

    ServerModule = types.ModuleType(RuntimeRoot + ".QingYunModLibs.ServerMod")
    ServerModule.ServerComp = FakeServerComp
    ServerModule.__all__ = ["ServerComp"]
    sys.modules[ServerModule.__name__] = ServerModule

    class FakeCombatMode(object):
        NATIVE = "native"
        FIGHT = "fight"

    class FakeStateType(object):
        ATTACK = "attack"
        SNEAKING = "sneaking"
        DEFENSE = "defense"
        DODGE = "dodge"

    ConstantsModule = types.ModuleType(RuntimeRoot + ".Core.Constants")
    ConstantsModule.MobCombatMode = FakeCombatMode
    ConstantsModule.MobCombatStateType = FakeStateType
    sys.modules[ConstantsModule.__name__] = ConstantsModule

    class FakeRegistry(object):
        @staticmethod
        def Entity(EntityType, Alias):
            return lambda ClassValue: ClassValue

    RegistryModule = types.ModuleType(RuntimeRoot + ".Core.Registry")
    RegistryModule.MobEntityRegistry = FakeRegistry
    sys.modules[RegistryModule.__name__] = RegistryModule

    BindModule = types.ModuleType(RuntimeRoot + ".Combat.FightStateSystem")
    BindModule.BindMobState = lambda EntityType, StateId: (lambda ClassValue: ClassValue)
    sys.modules[BindModule.__name__] = BindModule

    ModuleName = RuntimeRoot + ".Entities.WardenMob"
    Spec = importlib.util.spec_from_file_location(ModuleName, str(ENTITY_PATH))
    RuntimeModule = importlib.util.module_from_spec(Spec)
    sys.modules[ModuleName] = RuntimeModule
    Spec.loader.exec_module(RuntimeModule)
    WardenClass = RuntimeModule.WardenMob

    StatefulNativeComponents = {
        "minecraft:vibration_listener": {"keep": True},
        "minecraft:suspect_tracking": {"suspect": "runtime-state"},
        "minecraft:anger_level": {
            "anger": 95,
            "remove_targets_below_angry_threshold": True,
        },
        "minecraft:follow_range": 30,
    }
    OriginalComponents = copy.deepcopy(StatefulNativeComponents)
    OriginalComponents.update(copy.deepcopy(WardenClass.NativeControlComponentMap))
    OriginalComponents.update(copy.deepcopy(WardenClass.NativeMeleeAttackComponentMap))
    FakeServerComp.event = FakeEventComponent(OriginalComponents)
    Mob = WardenClass("warden-1")
    Mob.mode = FakeCombatMode.FIGHT
    Mob.on_combat_mode_changed(FakeCombatMode.NATIVE, FakeCombatMode.FIGHT)
    assert FakeServerComp.event.components == StatefulNativeComponents
    assert Mob.NativeControlSuppressed and Mob.NativeAttackSuppressed
    Mob.sync_fight_render_state()
    assert Mob.render_values["query.mod.fight"] == 1.0
    assert Mob.render_values["query.mod.fight_none"] == 1.0
    Mob.mode = FakeCombatMode.NATIVE
    Mob.on_combat_mode_changed(FakeCombatMode.FIGHT, FakeCombatMode.NATIVE)
    assert FakeServerComp.event.components == OriginalComponents
    assert not Mob.NativeControlSuppressed and not Mob.NativeAttackSuppressed
    Mob.sync_fight_render_state()
    assert Mob.render_values["query.mod.fight"] == 0.0
    assert Mob.render_values["query.mod.fight_none"] == 0.0

    # Codex 2026-08-10: 模拟 AddActorComponent 已返回 True、但本帧 GetComponents 尚未出现恢复项。
    FakeServerComp.event = FakeEventComponent(OriginalComponents)
    RetryMob = WardenClass("warden-retry")
    RetryMob.mode = FakeCombatMode.FIGHT
    RetryMob.on_combat_mode_changed(FakeCombatMode.NATIVE, FakeCombatMode.FIGHT)
    FakeServerComp.event.defer_add = True
    RetryMob.mode = FakeCombatMode.NATIVE
    RetryMob.on_combat_mode_changed(FakeCombatMode.FIGHT, FakeCombatMode.NATIVE)
    assert RetryMob.NativeControlSuppressed and RetryMob.NativeAttackSuppressed
    assert RetryMob.NativeControlRestoreMap and RetryMob.NativeAttackRestoreMap
    FakeServerComp.event.defer_add = False
    RetryMob.mode = FakeCombatMode.NATIVE
    RetryMob.on_tick(3)
    assert FakeServerComp.event.components == OriginalComponents
    assert not RetryMob.NativeControlSuppressed and not RetryMob.NativeAttackSuppressed
    assert RetryMob.NativeControlRestoreMap == {} and RetryMob.NativeAttackRestoreMap == {}

    # Codex 2026-08-10: 模拟旧实现已经误清空恢复快照，但原版组件仍实际缺失的存量实体。
    FakeServerComp.event = FakeEventComponent(StatefulNativeComponents)
    LostSnapshotMob = WardenClass("warden-lost-snapshot")
    LostSnapshotMob.mode = FakeCombatMode.NATIVE
    assert not LostSnapshotMob.NativeControlSuppressed and not LostSnapshotMob.NativeAttackSuppressed
    assert LostSnapshotMob.NativeControlRestoreMap == {} and LostSnapshotMob.NativeAttackRestoreMap == {}
    LostSnapshotMob.on_tick(9)
    assert FakeServerComp.event.components == OriginalComponents
    assert not LostSnapshotMob.NativeControlSuppressed and not LostSnapshotMob.NativeAttackSuppressed
    assert LostSnapshotMob.NativeControlRestoreMap == {} and LostSnapshotMob.NativeAttackRestoreMap == {}

    # Codex 2026-08-10: 旧实例也可能留下 suppressed 标记但丢失快照，自愈不能依赖该标记为 False。
    FakeServerComp.event = FakeEventComponent(StatefulNativeComponents)
    EmptySnapshotMob = WardenClass("warden-empty-snapshot")
    EmptySnapshotMob.mode = FakeCombatMode.NATIVE
    EmptySnapshotMob.NativeControlSuppressed = True
    EmptySnapshotMob.NativeAttackSuppressed = True
    EmptySnapshotMob.on_tick(12)
    assert FakeServerComp.event.components == OriginalComponents
    assert not EmptySnapshotMob.NativeControlSuppressed and not EmptySnapshotMob.NativeAttackSuppressed
    assert EmptySnapshotMob.NativeControlRestoreMap == {} and EmptySnapshotMob.NativeAttackRestoreMap == {}

    EmergingComponents = copy.deepcopy(OriginalComponents)
    EmergingComponents["minecraft:behavior.emerge"] = {"duration": 7.0}
    FakeServerComp.event = FakeEventComponent(EmergingComponents)
    EmergingMob = WardenClass("warden-2")
    assert EmergingMob.execute_fight_state("fight_attack_first") is False
    assert EmergingMob.mode == FakeCombatMode.NATIVE
    assert not EmergingMob.fight_controller.calls
    FakeServerComp.event.components.pop("minecraft:behavior.emerge")
    assert EmergingMob.execute_fight_state("fight_attack_first") is True
    assert EmergingMob.mode == FakeCombatMode.FIGHT
    assert EmergingMob.execute_fight_state("fight_none") is True
    assert EmergingMob.mode == FakeCombatMode.FIGHT

    EmergingMob.mode = FakeCombatMode.NATIVE
    assert EmergingMob.should_block_native_damage({"cause": "sonic_boom"}) is False
    EmergingMob.mode = FakeCombatMode.FIGHT
    assert EmergingMob.should_block_native_damage({"cause": "sonic_boom"}) is True
    assert EmergingMob.should_block_native_damage({"cause": "entity_attack"}, None) is True
    AttackState = types.SimpleNamespace(AttackState=True)
    assert EmergingMob.should_block_native_damage({"cause": "entity_attack"}, AttackState) is False
    assert EmergingMob.should_block_native_damage({"cause": "fire"}, None) is False
    return 11


if __name__ == "__main__":
    AnimationCount, ScaledCount = AssertAnimationNamespaceAndTiming()
    AttackStateCount, MotionSegmentCount = AssertAttackTimingsAndRootMotion()
    DodgeStateCount = AssertDodgeTimingsAndSmoke()
    BoneCount, UsedBoneCount = AssertGeometryAndBoneResolution()
    CaseCount, ControllerRefCount = AssertControllerAndRenderBindings()
    StateCount = AssertEntityDeployment()
    RuntimeCaseCount = AssertRuntimeComponentAndDamageTransitions()
    print(
        "warden deployment checks passed: animations=%d scaled=%d attack_states=%d motion_segments=%d dodge_states=%d bones=%d used_bones=%d cases=%d refs=%d states=%d runtime=%d"
        % (
            AnimationCount, ScaledCount, AttackStateCount, MotionSegmentCount,
            DodgeStateCount, BoneCount, UsedBoneCount, CaseCount,
            ControllerRefCount, StateCount, RuntimeCaseCount,
        )
    )
