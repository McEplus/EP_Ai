# coding=utf-8
"""铁傀儡战斗资源与脚本绑定的静态回归检查。"""

import ast
import json
import re
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[4]
RESOURCE_ROOT = PROJECT_ROOT / "src" / "SwordSoul_NewERA_R"
SCRIPT_ROOT = PROJECT_ROOT / "src" / "SwordSoul_NewERA_B" / "SwordSoulMobFightScripts"


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
    return Result


def ReadInitAssignments(PathValue, ClassName):
    Tree = ast.parse(PathValue.read_text(encoding="utf-8-sig"))
    ClassNode = next(
        Node for Node in Tree.body
        if isinstance(Node, ast.ClassDef) and Node.name == ClassName
    )
    InitNode = next(
        Node for Node in ClassNode.body
        if isinstance(Node, ast.FunctionDef) and Node.name == "__init__"
    )
    Result = {}
    for Node in InitNode.body:
        if not isinstance(Node, ast.Assign):
            continue
        Target = Node.targets[0]
        if not isinstance(Target, ast.Attribute) or not isinstance(Target.value, ast.Name):
            continue
        if Target.value.id != "self":
            continue
        try:
            Result[Target.attr] = ast.literal_eval(Node.value)
        except (ValueError, TypeError):
            continue
    return Result


def AssertGeometryAndAnimations():
    GeometryPath = RESOURCE_ROOT / "models" / "entity" / "mob" / "Iron_golem.geo.json"
    AnimationPath = RESOURCE_ROOT / "animations" / "mob" / "iron_golem" / "fight_iron_golem.animation.json"
    Geometry = ReadJson(GeometryPath)["minecraft:geometry"][0]
    Animations = ReadJson(AnimationPath)["animations"]
    Bones = Geometry["bones"]
    BoneMap = dict((Bone["name"], Bone) for Bone in Bones)
    assert len(BoneMap) == len(Bones), "duplicate geometry bone"
    assert Geometry["description"]["identifier"] == "geometry.better_iron_golem"
    for Bone in Bones:
        Parent = Bone.get("parent")
        assert not Parent or Parent in BoneMap, (Bone["name"], Parent)
    for BoneName in BoneMap:
        Seen = set()
        CurrentName = BoneName
        while BoneMap[CurrentName].get("parent"):
            assert CurrentName not in Seen, "geometry parent cycle: %s" % BoneName
            Seen.add(CurrentName)
            CurrentName = BoneMap[CurrentName]["parent"]
    assert BoneMap["root"].get("parent") is None
    assert all(Bone.get("parent") != "root_move" for Bone in Bones)
    assert BoneMap["fight_body"]["parent"] == "body"
    assert BoneMap["waist"]["parent"] == "fight_body"
    assert BoneMap["right_arm"]["parent"] == "arm0"
    assert BoneMap["left_arm"]["parent"] == "arm1"
    assert BoneMap["right_leg"]["parent"] == "leg0"
    assert BoneMap["left_leg"]["parent"] == "leg1"
    for BoneName in ("body", "head", "arm0", "arm1", "leg0", "leg1"):
        assert BoneName in BoneMap, BoneName
    UsedBones = set()
    for Animation in Animations.values():
        UsedBones.update((Animation.get("bones") or {}).keys())
    assert UsedBones <= set(BoneMap), sorted(UsedBones - set(BoneMap))
    # Codex 2026-08-04: 新增动作允许驱动无网格 body 包装骨，但不得回退驱动原版四肢包装骨。
    assert not ({"arm0", "arm1", "leg0", "leg1"} & UsedBones)
    assert "fight_body" in UsedBones
    assert len(Animations) == 21
    return len(Bones), len(Animations)


def AssertControllerAndRenderBindings():
    ControllerPath = RESOURCE_ROOT / "animation_controllers" / "iron_golem_fight.animation_controllers.json"
    StaticPath = SCRIPT_ROOT / "Render" / "StaticRenderConfig.py"
    Controller = ReadJson(ControllerPath)["animation_controllers"]["controller.animation.fight_iron_golem"]
    ControllerRefs = set()
    ExpectedBlend = {"0.05": 0.7, "0.1": 0.3, "0.15": 0.1, "0.2": 0.0}
    for CaseName, CaseData in Controller["case"].items():
        ControllerRefs.update(CaseData.get("animations", []))
        assert CaseData.get("blend_transition") == ExpectedBlend, "missing blend: %s" % CaseName
        assert CaseData.get("blend_via_shortest_path") is True, "missing shortest path: %s" % CaseName
    ExpectedFightRefs = {
        "iron_golem_attack_first", "iron_golem_attack_second", "iron_golem_attack_third",
        "iron_golem_attack_sprint", "iron_golem_sneaking", "iron_golem_attack_sneaking_1",
        "iron_golem_attack_sneaking_2", "iron_golem_try_defense", "iron_golem_common_defense",
        "iron_golem_perfect_defense", "iron_golem_attack_execute", "iron_golem_dodge_forward",
        "iron_golem_dodge_back", "iron_golem_dodge_right", "iron_golem_dodge_left",
        "iron_golem_attack_defense_1", "iron_golem_attack_defense_2",
        "iron_golem_hit_light", "iron_golem_hit_space", "iron_golem_hit_fall", "iron_golem_hit_heavy",
    }
    assert ControllerRefs == ExpectedFightRefs, ControllerRefs ^ ExpectedFightRefs
    # Codex 2026-08-04: 铁傀儡四方向让步闪必须复用同方向普通闪避动作短名。
    for Direction in ("forward", "back", "left", "right"):
        assert Controller["case"]["fight_all_budge_%s" % Direction]["animations"] == [
            "iron_golem_dodge_%s" % Direction
        ]
    Static = ReadClassAssignments(StaticPath, "IronGolemStaticRenderConfig")
    assert ControllerRefs <= set(Static["animation"])
    assert {
        "walk", "move", "attack", "flower", "look_at_target", "walk_to_target", "move_to_target",
    } <= set(Static["animation"])
    assert Static["animation_controller"] == {
        "c_move_controller": "controller.animation.iron_golem.move",
        "c_arm_controller": "controller.animation.iron_golem.arm_movement",
        "c_iron_golem_fight_controller": "controller.animation.fight_iron_golem",
    }
    assert Static["remove_animation_controller"] == [
        "controller__move_controller", "controller__arm_controller",
    ]
    assert Static["script_animate"] == {
        "look_at_target": "!query.mod.fight",
        "c_move_controller": "!query.mod.fight",
        "c_arm_controller": "!query.mod.fight",
        # Codex 2026-08-10: 所有控制器代理（含核心控制器）都必须使用 c_ 前缀。
        "c_iron_golem_fight_controller": "",
    }
    return len(ControllerRefs)


def AssertEntityBindingsAndComponents():
    EntityPath = SCRIPT_ROOT / "Entities" / "IronGolemMob.py"
    InitPath = SCRIPT_ROOT / "Entities" / "__init__.py"
    EntityText = EntityPath.read_text(encoding="utf-8")
    Tree = ast.parse(EntityText)
    AllowedNode = next(
        Node for Node in Tree.body
        if isinstance(Node, ast.Assign)
        and any(isinstance(Target, ast.Name) and Target.id == "IRON_GOLEM_ALLOWED_STATE_IDS" for Target in Node.targets)
    )
    Allowed = ast.literal_eval(AllowedNode.value)
    Bindings = set(re.findall(
        r'@BindMobState\(IRON_GOLEM_ENTITY_TYPE, "([^"]+)"\)',
        EntityText,
    ))
    assert Bindings == Allowed, Bindings ^ Allowed
    assert "from FightState.UseEmptyState import *" in EntityText
    assert "IronGolemState" not in EntityText
    assert "from . import IronGolemMob" in InitPath.read_text(encoding="utf-8")
    assert EntityText.count('@MobEntityRegistry.Entity(IRON_GOLEM_ENTITY_TYPE, "iron_golem")') == 1
    Entity = ReadClassAssignments(EntityPath, "IronGolemMob")
    assert Entity["aiIntellect"] == "mid"
    assert Entity["BaseKeepArmor"] == 1.2
    assert Entity["StateArmorProfileMap"] == {
        "common_attack": {"super_armor": 1.5},
    }
    # Codex 2026-08-04: 已制作动作不得继续留在强制反应降级表。
    assert "fight_attack_defense" not in Entity["FightReactionFallbackMap"]
    assert "fight_hit_heavy" not in Entity["FightReactionFallbackMap"]
    for Direction in ("forward", "back", "left", "right"):
        assert "fight_budge_%s" % Direction not in Entity["FightReactionFallbackMap"]
    assert Entity["NativeMeleeAttackComponentMap"] == {
        "minecraft:attack": {"damage": {"range_min": 7, "range_max": 21}},
        "minecraft:behavior.melee_box_attack": {"priority": 1, "track_target": True},
    }
    for RequiredControl in (
        "minecraft:movement", "minecraft:navigation.walk", "minecraft:movement.basic",
        "minecraft:behavior.move_towards_target", "minecraft:behavior.move_through_village",
        "minecraft:behavior.move_towards_dwelling_restriction", "minecraft:behavior.offer_flower",
        "minecraft:behavior.random_stroll", "minecraft:behavior.look_at_player",
        "minecraft:behavior.random_look_around",
    ):
        assert RequiredControl in Entity["NativeControlComponentMap"], RequiredControl
    assert "minecraft:player_created" in EntityText
    assert "minecraft:village_created" in EntityText
    assert 'get("cause") != "entity_attack"' in EntityText

    ExpectedStateBases = {
        "fight_attack_first": "EmptyAttackFirst",
        "fight_attack_second": "EmptyAttackSecond",
        "fight_attack_third": "EmptyAttackThird",
        "fight_attack_sprint": "EmptyAttackSprint",
        "fight_attack_execute": "EmptyAttackExecute",
        "fight_sneaking": "EmptySneaking",
        "fight_attack_sneaking_1": "EmptyAttackSneaking1",
        "fight_attack_sneaking_2": "EmptyAttackSneaking2",
        "fight_attack_defense": "EmptyAttackDefense",
        "fight_try_defense": "EmptyTryDefense",
        "fight_common_defense": "EmptyCommonDefense",
        "fight_perfect_defense": "EmptyPerfectDefense",
        "fight_dodge_forward": "EmptyDodgeForward",
        "fight_dodge_back": "EmptyDodgeBack",
        "fight_dodge_left": "EmptyDodgeLeft",
        "fight_dodge_right": "EmptyDodgeRight",
        "fight_budge_forward": "EmptyBudgeForward",
        "fight_budge_back": "EmptyBudgeBack",
        "fight_budge_left": "EmptyBudgeLeft",
        "fight_budge_right": "EmptyBudgeRight",
        "fight_hit_light": "EmptyHitLight",
        "fight_hit_space": "EmptyHitSpace",
        "fight_hit_heavy": "EmptyHitHeavy",
    }
    BoundStateBases = {}
    for Node in Tree.body:
        if not isinstance(Node, ast.ClassDef):
            continue
        for Decorator in Node.decorator_list:
            if not isinstance(Decorator, ast.Call) or not isinstance(Decorator.func, ast.Name):
                continue
            if Decorator.func.id != "BindMobState" or len(Decorator.args) < 2:
                continue
            StateId = ast.literal_eval(Decorator.args[1])
            BaseName = Node.bases[0].id if isinstance(Node.bases[0], ast.Name) else None
            BoundStateBases[StateId] = BaseName
            InitNode = next(
                Child for Child in Node.body
                if isinstance(Child, ast.FunctionDef) and Child.name == "__init__"
            )
            assert any(
                isinstance(Call, ast.Call)
                and isinstance(Call.func, ast.Attribute)
                and isinstance(Call.func.value, ast.Name)
                and Call.func.value.id == BaseName
                and Call.func.attr == "__init__"
                for Call in ast.walk(InitNode)
            ), "state wrapper must call shared init: %s" % StateId
    assert BoundStateBases == ExpectedStateBases, BoundStateBases
    assert not any(
        isinstance(Node, ast.ClassDef)
        and Node.name.startswith("IronGolem")
        and Node.name != "IronGolemMob"
        for Node in Tree.body
    )

    BasePath = SCRIPT_ROOT / "Entities" / "BaseMob.py"
    ControllerPath = SCRIPT_ROOT / "Combat" / "FightController.py"
    BaseText = BasePath.read_text(encoding="utf-8")
    ControllerText = ControllerPath.read_text(encoding="utf-8")
    assert "BaseKeepArmor = 0.0" in BaseText
    assert "StateArmorProfileMap = {}" in BaseText
    assert "StateArmorOverrideMap = {}" in BaseText
    assert "self.sync_base_keep_armor()" in BaseText
    assert "self.mob.get_state_armor_profile_map().get(stateType, {})" in ControllerText
    assert "self.mob.get_state_armor_override_map().get(stateId, {})" in ControllerText
    assert "self.mob.get_base_keep_armor()" in ControllerText
    return len(Bindings)


def AssertSharedStateTiming():
    StatePath = SCRIPT_ROOT / "Entities" / "FightState" / "IronGolemState.py"
    # Codex 2026-08-03: 禁止回归到铁傀儡专属状态文件；动作资源自行适配共享状态时长。
    assert not StatePath.exists(), "mob-specific state file must not exist"
    SharedStatePath = SCRIPT_ROOT / "Entities" / "FightState" / "UseEmptyState.py"
    EntityPath = SCRIPT_ROOT / "Entities" / "IronGolemMob.py"
    AnimationPath = RESOURCE_ROOT / "animations" / "mob" / "iron_golem" / "fight_iron_golem.animation.json"
    Animations = ReadJson(AnimationPath)["animations"]
    AnimationStateMap = {
        "animation.fight_iron_golem.attack_first": "EmptyAttackFirst",
        "animation.fight_iron_golem.attack_second": "EmptyAttackSecond",
        "animation.fight_iron_golem.attack_third": "EmptyAttackThird",
        "animation.fight_iron_golem.attack_sprint": "EmptyAttackSprint",
        "animation.fight_iron_golem.attack_execute": "EmptyAttackExecute",
        "animation.fight_iron_golem.attack_sneaking_1": "EmptyAttackSneaking1",
        "animation.fight_iron_golem.attack_sneaking_2": "EmptyAttackSneaking2",
        "animation.fight_iron_golem.attack_defense_1": "EmptyAttackDefense",
        "animation.fight_iron_golem.attack_defense_2": "EmptyAttackDefense",
        "animation.fight_iron_golem.common_defense": "EmptyCommonDefense",
        "animation.fight_iron_golem.perfect_defense": "EmptyPerfectDefense",
        "animation.fight_iron_golem.dodge_forward": "EmptyDodgeForward",
        "animation.fight_iron_golem.dodge_back": "EmptyDodgeBack",
        "animation.fight_iron_golem.dodge_left": "EmptyDodgeLeft",
        "animation.fight_iron_golem.dodge_right": "EmptyDodgeRight",
        "animation.fight_iron_golem.hit_light": "EmptyHitLight",
        "animation.fight_iron_golem.hit_space": "EmptyHitSpace",
        "animation.fight_iron_golem.hit_heavy": "EmptyHitHeavy",
    }
    PlaybackScaleCount = 0
    for AnimationName, StateClassName in AnimationStateMap.items():
        Animation = Animations[AnimationName]
        StateTime = float(ReadInitAssignments(SharedStatePath, StateClassName)["StateAnimTime"])
        # Codex 2026-08-04: 三段普攻当前在铁傀儡薄包装类中声明实体时序，校验运行时实际值。
        WrapperAssignments = ReadInitAssignments(EntityPath, StateClassName.replace("Empty", "", 1))
        StateTime = float(WrapperAssignments.get("StateAnimTime", StateTime))
        Expression = Animation.get("anim_time_update")
        PlaybackScale = 1.0
        if Expression:
            Match = re.fullmatch(
                r"query\.anim_time \+ query\.delta_time \* ([0-9]+(?:\.[0-9]+)?)",
                Expression,
            )
            assert Match, "invalid anim_time_update: %s" % AnimationName
            PlaybackScale = float(Match.group(1))
            PlaybackScaleCount += 1
        LogicalDuration = float(Animation["animation_length"]) / PlaybackScale
        assert abs(LogicalDuration - StateTime) < 0.000001, (
            AnimationName, LogicalDuration, StateTime
        )
    assert PlaybackScaleCount == 17
    return len(AnimationStateMap), PlaybackScaleCount


def Main():
    # Codex 2026-08-03: 把首次部署的关键契约固化为可重复执行的静态检查。
    BoneCount, AnimationCount = AssertGeometryAndAnimations()
    ControllerCount = AssertControllerAndRenderBindings()
    StateCount = AssertEntityBindingsAndComponents()
    SharedStateCount, PlaybackScaleCount = AssertSharedStateTiming()
    print(
        "iron golem deployment valid: bones=%d animations=%d controller_refs=%d states=%d shared_states=%d playback_scales=%d"
        % (BoneCount, AnimationCount, ControllerCount, StateCount, SharedStateCount, PlaybackScaleCount)
    )


if __name__ == "__main__":
    Main()
