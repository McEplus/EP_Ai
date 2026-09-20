# coding=utf-8
"""生物合集六种生物的服务端、资源、原版链和生命周期部署回归。"""

import ast
import copy
import json
import re
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[4]
RESOURCE_ROOT = PROJECT_ROOT / "src" / "SwordSoul_NewERA_R"
SCRIPT_ROOT = PROJECT_ROOT / "src" / "SwordSoul_NewERA_B" / "SwordSoulMobFightScripts"
ENTITY_ROOT = SCRIPT_ROOT / "Entities"
STATIC_PATH = SCRIPT_ROOT / "Render" / "StaticRenderConfig.py"
MOD_MAIN_PATH = SCRIPT_ROOT / "modMain.py"
ENTITY_INIT_PATH = ENTITY_ROOT / "__init__.py"


COMMON_BLEND = {"0.05": 0.7, "0.1": 0.3, "0.15": 0.1, "0.2": 0.0}
LOGICAL_DURATIONS = {
    "attack_first": 1.5,
    "attack_second": 1.3,
    "attack_third": 1.3,
    "attack_sprint": 2.04,
    "attack_execute": 2.72,
    "attack_sneaking_1": 1.65,
    "attack_sneaking_2": 3.3,
    "attack_defense_1": 0.44,
    "attack_defense_2": 0.44,
    "common_defense": 0.8,
    "perfect_defense": 0.56,
    "dodge_forward": 1.75,
    "dodge_back": 1.75,
    "dodge_left": 1.75,
    "dodge_right": 1.75,
    "hit_light": 1.0,
    "hit_space": 1.0,
    "hit_fall": 1.0,
    "hit_heavy": 2.75,
}


def StateSet(*Names):
    return set(Names)


COMMON_MOBILE_STATES = StateSet(
    "fight_attack_first",
    "fight_attack_second",
    "fight_attack_third",
    "fight_attack_sprint",
    "fight_sneaking",
    "fight_attack_sneaking_1",
    "fight_attack_sneaking_2",
    "fight_dodge_forward",
    "fight_dodge_back",
    "fight_dodge_left",
    "fight_dodge_right",
    "fight_budge_forward",
    "fight_budge_back",
    "fight_budge_left",
    "fight_budge_right",
    "fight_hit_light",
    "fight_hit_space",
)


MOBS = {
    "spider": {
        "class": "SpiderMob",
        "entity": "minecraft:spider",
        "prefix": "animation.fight_spider.",
        "geometry": {"default": "geometry.fight_spider"},
        "states": COMMON_MOBILE_STATES | StateSet(
            "fight_attack_defense", "fight_try_defense", "fight_hit_heavy",
        ),
        "direct_reaction_bases": {
            "fight_attack_defense": "EmptyAttackDefense",
            "fight_hit_heavy": "EmptyHitHeavy",
        },
        "specialized_states": (COMMON_MOBILE_STATES - StateSet("fight_sneaking")) | StateSet(
            "fight_attack_defense", "fight_hit_heavy",
        ),
        # Codex 2026-08-10: 蜘蛛直接以 BBModel 原始秒表播放，状态窗口也按同一原始时钟标定，不做公共动作重定时。
        "native_animation_clock": True,
        "native_animations": {
            "default_leg_pose": "animation.spider.default_leg_pose",
            "look_at_target": "animation.spider.look_at_target",
            "walk": "animation.spider.walk",
        },
        "controller_proxy_prefix": True,
        "native_controllers": {"move": "controller.animation.spider.move"},
        "required_control": {
            "minecraft:environment_sensor", "minecraft:on_target_acquired", "minecraft:angry",
        },
        "required_attack": {"minecraft:attack", "minecraft:behavior.melee_box_attack"},
    },
    "blaze": {
        "class": "BlazeMob",
        "entity": "minecraft:blaze",
        "prefix": "animation.fight_blaze.",
        "geometry": {"default": "geometry.fight_blaze"},
        "states": StateSet(
            "fight_attack_first", "fight_attack_second", "fight_attack_third",
            "fight_attack_execute", "fight_sneaking", "fight_attack_sneaking_1",
            "fight_attack_sneaking_2", "fight_try_defense", "fight_common_defense",
            "fight_perfect_defense", "fight_hit_light", "fight_hit_space",
        ),
        "native_animations": {
            "look_at_target": "animation.common.look_at_target",
            "move": "animation.blaze.move",
        },
        "native_controllers": {
            "move": "controller.animation.blaze.move",
            "flame": "controller.animation.blaze.flame",
        },
        "required_control": {
            "minecraft:target_nearby_sensor", "minecraft:on_hurt",
            "minecraft:on_hurt_by_player",
        },
        "required_attack": {
            "minecraft:attack", "minecraft:behavior.melee_box_attack",
            "minecraft:shooter", "minecraft:behavior.ranged_attack",
        },
    },
    "enderman": {
        "class": "EndermanMob",
        "entity": "minecraft:enderman",
        "prefix": "animation.fight_enderman.",
        "geometry": {"default": "geometry.better_enderman"},
        "states": COMMON_MOBILE_STATES | StateSet(
            "fight_attack_execute", "fight_attack_defense", "fight_try_defense",
            "fight_common_defense", "fight_perfect_defense", "fight_hit_heavy",
        ),
        "direct_reaction_bases": {
            "fight_attack_defense": "EmptyAttackDefense",
            "fight_hit_heavy": "EmptyHitHeavy",
        },
        "specialized_states": StateSet(
            "fight_attack_first", "fight_attack_second", "fight_attack_third",
            "fight_attack_sprint", "fight_attack_execute",
            "fight_sneaking", "fight_attack_sneaking_1", "fight_attack_sneaking_2",
            "fight_attack_defense", "fight_try_defense", "fight_common_defense", "fight_perfect_defense",
            "fight_dodge_forward", "fight_dodge_back", "fight_dodge_left", "fight_dodge_right",
            "fight_budge_forward", "fight_budge_back", "fight_budge_left", "fight_budge_right",
            "fight_hit_light", "fight_hit_space", "fight_hit_heavy",
        ),
        "native_animations": {
            "look_at_target_default": "animation.humanoid.look_at_target.default",
            "look_at_target_gliding": "animation.humanoid.look_at_target.gliding",
            "look_at_target_swimming": "animation.humanoid.look_at_target.swimming",
            "move": "animation.humanoid.move",
            "attack.rotations": "animation.humanoid.attack.rotations",
            "bob": "animation.humanoid.bob",
            "base_pose": "animation.enderman.base_pose",
            "arms_legs": "animation.enderman.arms_legs",
            "carrying": "animation.enderman.carrying",
            "scary_face": "animation.enderman.scary_face",
        },
        "controller_proxy_prefix": True,
        "native_controllers": {
            "look_at_target": "controller.animation.humanoid.look_at_target",
            "move": "controller.animation.humanoid.move",
            "attack": "controller.animation.humanoid.attack",
            "bob": "controller.animation.humanoid.bob",
            "base_pose": "controller.animation.enderman.base_pose",
            "carrying": "controller.animation.enderman.carrying",
            "scary_face": "controller.animation.enderman.scary_face",
        },
        "required_control": {
            "minecraft:movement", "minecraft:on_target_acquired",
            "minecraft:behavior.enderman_leave_block", "minecraft:behavior.enderman_take_block",
        },
        "required_hard_control": {"minecraft:teleport"},
        "required_attack": {"minecraft:attack", "minecraft:behavior.melee_box_attack"},
    },
    "ghast": {
        "class": "GhastMob",
        "entity": "minecraft:ghast",
        "prefix": "animation.arris_ghast.",
        "geometry": {"default": "geometry.fight_ghast"},
        "states": StateSet(
            "fight_attack_first", "fight_attack_second", "fight_attack_third",
            "fight_attack_defense", "fight_hit_light", "fight_hit_space",
        ),
        "native_animations": {"move": "animation.ghast.move"},
        "native_controllers": {"move": "controller.animation.ghast.move"},
        "required_control": {
            "minecraft:movement", "minecraft:navigation.float",
            "minecraft:behavior.float_wander",
        },
        "required_attack": {"minecraft:shooter", "minecraft:behavior.ranged_attack"},
    },
    "slime": {
        "class": "SlimeMob",
        "entity": "minecraft:slime",
        "prefix": "animation.arris_slime.",
        "geometry": {
            "default": "geometry.fight_slime",
            "armor": "geometry.fight_slime.armor",
        },
        "states": COMMON_MOBILE_STATES,
        "native_animations": {},
        "native_controllers": {},
        "required_control": {
            "minecraft:movement", "minecraft:movement.jump",
            "minecraft:on_target_acquired", "minecraft:on_target_escape",
        },
        "required_attack": {
            "minecraft:attack", "minecraft:area_attack", "minecraft:behavior.slime_attack",
        },
    },
    "ravager": {
        "class": "RavagerMob",
        "entity": "minecraft:ravager",
        "prefix": "animation.arris_ravager.",
        "geometry": {"default": "geometry.fight_ravager"},
        "states": COMMON_MOBILE_STATES | StateSet(
            "fight_attack_defense", "fight_hit_heavy",
        ),
        "direct_reaction_bases": {
            "fight_attack_defense": "EmptyAttackDefense",
            "fight_hit_heavy": "EmptyHitHeavy",
        },
        "specialized_states": StateSet(
            "fight_attack_first", "fight_attack_second", "fight_attack_third",
            "fight_attack_sprint", "fight_attack_sneaking_1", "fight_attack_sneaking_2",
            "fight_dodge_forward", "fight_dodge_back", "fight_dodge_left", "fight_dodge_right",
            "fight_budge_forward", "fight_budge_back", "fight_budge_left", "fight_budge_right",
        ),
        "native_animations": {
            "walk": "animation.ravager.walk",
            "look_at_target": "animation.common.look_at_target",
            "idle_mouth": "animation.ravager.idle_mouth",
            "stunned": "animation.ravager.stunned",
            "roaring": "animation.ravager.roaring",
            "biting": "animation.ravager.biting",
        },
        "controller_proxy_prefix": True,
        "native_controllers": {
            "move": "controller.animation.ravager.move",
            "head": "controller.animation.ravager.head_movement",
        },
        "required_control": {
            "minecraft:movement", "minecraft:ravager_blocked",
            "minecraft:behavior.move_to_village", "minecraft:behavior.celebrate",
        },
        "required_attack": {
            "minecraft:attack", "minecraft:behavior.delayed_attack",
            "minecraft:behavior.knockback_roar",
        },
    },
}


def ReadJson(PathValue):
    return json.loads(PathValue.read_text(encoding="utf-8-sig"))


def StripJsonComments(Source):
    Result = []
    Index = 0
    Quote = None
    Escaped = False
    while Index < len(Source):
        Character = Source[Index]
        if Quote:
            Result.append(Character)
            if Escaped:
                Escaped = False
            elif Character == "\\":
                Escaped = True
            elif Character == Quote:
                Quote = None
            Index += 1
            continue
        if Character == '"':
            Quote = Character
            Result.append(Character)
            Index += 1
            continue
        if Source[Index:Index + 2] == "//":
            Index += 2
            while Index < len(Source) and Source[Index] not in "\r\n":
                Index += 1
            continue
        if Source[Index:Index + 2] == "/*":
            Index += 2
            while Index + 1 < len(Source) and Source[Index:Index + 2] != "*/":
                Index += 1
            Index += 2
            continue
        Result.append(Character)
        Index += 1
    return re.sub(r",\s*([}\]])", r"\1", "".join(Result))


def ReadJsonWithComments(PathValue):
    return json.loads(StripJsonComments(PathValue.read_text(encoding="utf-8-sig")))


def ReadAssignments(ClassNode):
    Result = {}
    for Node in ClassNode.body:
        if not isinstance(Node, ast.Assign) or not isinstance(Node.targets[0], ast.Name):
            continue
        try:
            Result[Node.targets[0].id] = ast.literal_eval(Node.value)
        except (ValueError, TypeError):
            continue
    return Result


def FindNamedClass(Tree, Name):
    return next(Node for Node in Tree.body if isinstance(Node, ast.ClassDef) and Node.name == Name)


def ReadAllowedAndBindings(PathValue):
    Tree = ast.parse(PathValue.read_text(encoding="utf-8-sig"))
    Allowed = next(
        ast.literal_eval(Node.value)
        for Node in Tree.body
        if isinstance(Node, ast.Assign)
        and isinstance(Node.targets[0], ast.Name)
        and Node.targets[0].id.endswith("_ALLOWED_STATE_IDS")
    )
    Bindings = {}
    for ClassNode in (Node for Node in Tree.body if isinstance(Node, ast.ClassDef)):
        for Decorator in ClassNode.decorator_list:
            if not (
                isinstance(Decorator, ast.Call)
                and isinstance(Decorator.func, ast.Name)
                and Decorator.func.id == "BindMobState"
            ):
                continue
            Bindings[ast.literal_eval(Decorator.args[1])] = ClassNode
    return set(Allowed), Bindings, Tree


def FindStaticClasses():
    Tree = ast.parse(STATIC_PATH.read_text(encoding="utf-8-sig"))
    Result = {}
    for ClassNode in (Node for Node in Tree.body if isinstance(Node, ast.ClassDef)):
        for Decorator in ClassNode.decorator_list:
            if not isinstance(Decorator, ast.Call) or len(Decorator.args) < 2:
                continue
            Function = Decorator.func
            if not (
                isinstance(Function, ast.Attribute)
                and Function.attr == "Actor"
                and isinstance(Function.value, ast.Name)
                and Function.value.id == "MobStaticRenderRegistry"
            ):
                continue
            Result[ast.literal_eval(Decorator.args[0])] = (
                ast.literal_eval(Decorator.args[1]),
                ClassNode,
                ReadAssignments(ClassNode),
            )
    return Result


def ScriptAnimateMap(Value):
    if isinstance(Value, dict):
        return dict(Value)
    Result = {}
    for Entry in Value:
        if isinstance(Entry, dict):
            Key = Entry.get("key", Entry.get("name"))
            Result[Key] = Entry.get("condition", Entry.get("value", ""))
        else:
            Result[Entry[0]] = Entry[1]
    return Result


def FindResourceDocuments():
    AnimationDocuments = []
    GeometryDocuments = []
    for PathValue in (RESOURCE_ROOT / "animations" / "mob").rglob("*.animation.json"):
        Document = ReadJson(PathValue)
        if "animations" in Document:
            AnimationDocuments.append((PathValue, Document["animations"]))
    for PathValue in (RESOURCE_ROOT / "models" / "entity" / "mob").rglob("*.geo.json"):
        Document = ReadJson(PathValue)
        for Geometry in Document.get("minecraft:geometry", []):
            GeometryDocuments.append((PathValue, Geometry))
    return AnimationDocuments, GeometryDocuments


def FindSingleAnimationDocument(AnimationDocuments, Prefix):
    Matches = [
        (PathValue, Animations)
        for PathValue, Animations in AnimationDocuments
        if any(Name.startswith(Prefix) for Name in Animations)
    ]
    assert len(Matches) == 1, (Prefix, [str(Item[0]) for Item in Matches])
    return Matches[0]


def FindGeometry(GeometryDocuments, Identifier):
    Matches = [
        (PathValue, Geometry)
        for PathValue, Geometry in GeometryDocuments
        if Geometry.get("description", {}).get("identifier") == Identifier
    ]
    assert len(Matches) == 1, (Identifier, [str(Item[0]) for Item in Matches])
    return Matches[0]


def FindBBModel(MobName):
    Matches = list(PROJECT_ROOT.glob("*/*/fight_" + MobName + ".bbmodel"))
    assert len(Matches) == 1, (MobName, Matches)
    return Matches[0]


def ReadControllerReferences(Controller):
    References = set()
    for CaseData in Controller["case"].values():
        for Reference in CaseData.get("animations", []):
            References.add(next(iter(Reference)) if isinstance(Reference, dict) else Reference)
    return References


def StateMolangToken(StateId):
    if (
        StateId.startswith("fight_attack_")
        or StateId == "fight_sneaking"
        or StateId in ("fight_try_defense", "fight_common_defense", "fight_perfect_defense")
    ):
        return "use_empty_" + StateId[len("fight_"):]
    return "fight_all_" + StateId[len("fight_"):]


def AssertEntityModules():
    TotalStates = 0
    ModMain = MOD_MAIN_PATH.read_text(encoding="utf-8-sig")
    EntityInit = ENTITY_INIT_PATH.read_text(encoding="utf-8-sig")
    ForbiddenTargetComponents = {
        "minecraft:behavior.nearest_attackable_target",
        "minecraft:behavior.hurt_by_target",
    }
    for MobName, Config in MOBS.items():
        PathValue = ENTITY_ROOT / (Config["class"] + ".py")
        Source = PathValue.read_text(encoding="utf-8-sig")
        compile(Source, str(PathValue), "exec")
        Allowed, Bindings, Tree = ReadAllowedAndBindings(PathValue)
        assert Allowed == Config["states"], (MobName, Allowed ^ Config["states"])
        assert set(Bindings) == Allowed, (MobName, set(Bindings) ^ Allowed)
        SpecializedStates = Config.get("specialized_states", set())
        for StateId, ClassNode in Bindings.items():
            HasMethods = any(isinstance(Node, ast.FunctionDef) for Node in ClassNode.body)
            assert HasMethods == (StateId in SpecializedStates), (MobName, StateId)
        EntityClass = FindNamedClass(Tree, Config["class"])
        Assignments = ReadAssignments(EntityClass)
        ReactionBases = Config.get("direct_reaction_bases", {})
        FallbackMap = Assignments.get("FightReactionFallbackMap", {})
        assert not set(ReactionBases) & set(FallbackMap), MobName
        for StateId, BaseName in ReactionBases.items():
            Bases = Bindings[StateId].bases
            assert len(Bases) == 1 and isinstance(Bases[0], ast.Name)
            assert Bases[0].id == BaseName, (MobName, StateId, Bases[0])
        ControlMap = Assignments["NativeControlComponentMap"]
        AttackMap = Assignments["NativeMeleeAttackComponentMap"]
        HardControl = set()
        TeleportComponentName = Assignments.get("NativeTeleportComponentName")
        if TeleportComponentName:
            HardControl.add(TeleportComponentName)
        assert not set(ControlMap) & set(AttackMap), MobName
        assert not HardControl & (set(ControlMap) | set(AttackMap)), MobName
        assert Config["required_control"] <= set(ControlMap), MobName
        assert Config.get("required_hard_control", set()) <= HardControl, MobName
        assert Config["required_attack"] <= set(AttackMap), MobName
        assert not ForbiddenTargetComponents & (set(ControlMap) | set(AttackMap)), MobName
        EntityDecorators = [
            Decorator for Decorator in EntityClass.decorator_list
            if isinstance(Decorator, ast.Call)
        ]
        assert len(EntityDecorators) == 1
        ModuleConstants = {}
        for Node in Tree.body:
            if not isinstance(Node, ast.Assign) or not isinstance(Node.targets[0], ast.Name):
                continue
            try:
                ModuleConstants[Node.targets[0].id] = ast.literal_eval(Node.value)
            except (ValueError, TypeError):
                continue
        EntityArgument = EntityDecorators[0].args[0]
        EntityValue = (
            ModuleConstants[EntityArgument.id]
            if isinstance(EntityArgument, ast.Name)
            else ast.literal_eval(EntityArgument)
        )
        assert EntityValue == Config["entity"]
        assert ast.literal_eval(EntityDecorators[0].args[1]) == MobName
        assert 'Mod.ServerInit("Entities.%s")' % Config["class"] in ModMain
        assert "from . import " + Config["class"] in EntityInit
        TotalStates += len(Allowed)
    assert TotalStates == 97
    return len(MOBS), TotalStates


def AssertStaticAndControllers(AnimationDocuments):
    StaticClasses = FindStaticClasses()
    Aliases = set()
    TotalCases = 0
    TotalRegisteredAnimations = 0
    for MobName, Config in MOBS.items():
        Alias, _, Assignments = StaticClasses[Config["entity"]]
        assert Alias == MobName
        assert Alias not in Aliases
        Aliases.add(Alias)
        assert Assignments["geometry"] == Config["geometry"]
        AnimationMap = Assignments["animation"]
        ControllerMap = Assignments["animation_controller"]
        for Key, Value in Config["native_animations"].items():
            assert AnimationMap.get(Key) == Value, (MobName, Key)
        # Codex 2026-08-10: 目标生物的控制器代理必须以 c_ 与动画代理命名空间分离。
        ControllerPrefix = "c_" if Config.get("controller_proxy_prefix") else ""
        for Key, Value in Config["native_controllers"].items():
            ProxyKey = ControllerPrefix + Key
            assert ControllerMap.get(ProxyKey) == Value, (MobName, ProxyKey)
        ExpectedRemoved = set("controller__" + Key for Key in Config["native_controllers"])
        assert set(Assignments["remove_animation_controller"]) == ExpectedRemoved
        ScriptMap = ScriptAnimateMap(Assignments["script_animate"])
        for Key in Config["native_controllers"]:
            ProxyKey = ControllerPrefix + Key
            assert "!query.mod.fight" in ScriptMap.get(ProxyKey, ""), (MobName, ProxyKey, ScriptMap)
        CoreController = "controller.animation.fight_" + MobName
        CoreKeys = [Key for Key, Value in ControllerMap.items() if Value == CoreController]
        assert len(CoreKeys) == 1, (MobName, CoreKeys)
        if Config.get("controller_proxy_prefix"):
            assert all(Key.startswith("c_") for Key in ControllerMap), (MobName, ControllerMap)
        assert ScriptMap.get(CoreKeys[0]) == ""

        _, Exported = FindSingleAnimationDocument(AnimationDocuments, Config["prefix"])
        AuthoredNames = set(Exported)
        RuntimeNames = set(AuthoredNames)
        if MobName == "ravager":
            RuntimeNames.remove("animation.arris_ravager.attack1_to_3")
            assert "animation.arris_ravager.sprint" in RuntimeNames
            assert "animation.arris_ravager.sprin" not in AuthoredNames
        for Name in RuntimeNames:
            assert Name in AnimationMap.values(), (MobName, Name)
        assert "animation.arris_ravager.attack1_to_3" not in AnimationMap.values()
        TotalRegisteredAnimations += len(RuntimeNames)

        ControllerPath = RESOURCE_ROOT / "animation_controllers" / "mob" / (MobName + "_fight.animation_controllers.json")
        ControllerDocument = ReadJson(ControllerPath)
        Controller = ControllerDocument["animation_controllers"][CoreController]
        assert Controller["switch"] == "query.mod.{&}"
        CaseTokens = set()
        for CaseName, CaseData in Controller["case"].items():
            assert CaseData.get("blend_transition") == COMMON_BLEND, (MobName, CaseName)
            assert CaseData.get("blend_via_shortest_path") is True, (MobName, CaseName)
            if CaseName != "default":
                CaseTokens.add(CaseName.split(" &&", 1)[0])
        ExpectedTokens = set(StateMolangToken(StateId) for StateId in Config["states"])
        assert CaseTokens == ExpectedTokens, (MobName, CaseTokens ^ ExpectedTokens)
        RegisteredKeys = set(AnimationMap) | set(ControllerMap)
        References = ReadControllerReferences(Controller)
        assert References <= RegisteredKeys, (MobName, References - RegisteredKeys)
        assert not any("attack1_to_3" in Reference for Reference in References)
        if MobName == "ravager":
            assert Controller["case"]["use_empty_attack_defense && query.mod.defense_state"]["animations"] == [
                "ravager_attack_defense_1"
            ]
            assert Controller["case"]["use_empty_attack_defense && !query.mod.defense_state"]["animations"] == [
                "ravager_attack_defense_2"
            ]
            assert Controller["case"]["fight_all_hit_heavy"]["animations"] == ["ravager_hit_heavy"]
        TotalCases += len(Controller["case"])
    assert TotalRegisteredAnimations == 85
    return len(Aliases), TotalRegisteredAnimations, TotalCases


def AssertAnimationTimingAndGeometry(AnimationDocuments, GeometryDocuments):
    TotalAnimations = 0
    GeometryIdentifiers = set()
    for MobName, Config in MOBS.items():
        BBModel = ReadJson(FindBBModel(MobName))
        BBAnimations = dict((Animation["name"], Animation) for Animation in BBModel["animations"])
        AnimationPath, Exported = FindSingleAnimationDocument(AnimationDocuments, Config["prefix"])
        assert set(Exported) == set(BBAnimations), MobName
        for Name, Animation in Exported.items():
            Source = BBAnimations[Name]
            assert abs(float(Animation.get("animation_length", 0.0)) - float(Source["length"])) < 0.00005
            Suffix = Name.rsplit(".", 1)[-1]
            Expression = Animation.get("anim_time_update", "")
            if Config.get("native_animation_clock"):
                assert not Expression, (MobName, Suffix, Expression)
            elif Suffix in LOGICAL_DURATIONS and float(Source["length"]) > 0.0:
                Match = re.fullmatch(r"query\.anim_time \+ query\.delta_time \* ([0-9.]+)", Expression)
                assert Match, (MobName, Suffix, Expression)
                Rate = float(Match.group(1))
                assert abs(float(Source["length"]) / Rate - LOGICAL_DURATIONS[Suffix]) < 0.0001
            else:
                assert not Expression, (MobName, Suffix, Expression)
        SlimeSneaking = Exported.get("animation.arris_slime.sneaking")
        if SlimeSneaking is not None:
            assert SlimeSneaking.get("loop") is True

        GeometryById = {}
        for Identifier in Config["geometry"].values():
            GeometryPath, Geometry = FindGeometry(GeometryDocuments, Identifier)
            GeometryById[Identifier] = Geometry
            GeometryIdentifiers.add(Identifier)
            Bones = Geometry["bones"]
            BoneMap = dict((Bone["name"], Bone) for Bone in Bones)
            assert len(BoneMap) == len(Bones), Identifier
            RootMove = BoneMap.get("root_move")
            if RootMove is not None:
                # Codex 2026-08-09: 位移数据骨必须为空且独立，防止客户端可见模型重复应用服务端位移。
                assert not RootMove.get("parent"), (Identifier, RootMove)
                assert not RootMove.get("cubes"), (Identifier, RootMove)
                assert not RootMove.get("locators"), (Identifier, RootMove)
            for Bone in Bones:
                Parent = Bone.get("parent")
                assert not Parent or Parent in BoneMap, (Identifier, Bone["name"], Parent)
                Seen = set()
                Current = Bone
                while Current.get("parent"):
                    assert Current["name"] not in Seen, (Identifier, Current["name"])
                    Seen.add(Current["name"])
                    Current = BoneMap[Current["parent"]]
            for Bone in Bones:
                if Bone["name"] == "root_move":
                    continue
                Current = Bone
                while Current.get("parent"):
                    assert Current["parent"] != "root_move", (Identifier, Bone["name"])
                    Current = BoneMap[Current["parent"]]
            UsedBones = set()
            for Animation in Exported.values():
                UsedBones.update((Animation.get("bones") or {}).keys())
            assert UsedBones <= set(BoneMap), (MobName, sorted(UsedBones - set(BoneMap)), AnimationPath)
        if MobName == "slime":
            MainBones = set(Bone["name"] for Bone in GeometryById["geometry.fight_slime"]["bones"])
            ArmorBones = set(Bone["name"] for Bone in GeometryById["geometry.fight_slime.armor"]["bones"])
            assert MainBones == ArmorBones
        if MobName == "ravager":
            RavagerBones = GeometryById["geometry.fight_ravager"]["bones"]
            assert any("stun" in (Bone.get("locators") or {}) for Bone in RavagerBones)
        if MobName == "ghast":
            _, ActiveResourceRoot = ActiveGameRoots()
            NativeGeometry = ReadJson(ActiveResourceRoot / "models" / "entity" / "ghast.geo.json")
            NativeGeometry = NativeGeometry["minecraft:geometry"][0]
            FightGeometry = copy.deepcopy(GeometryById["geometry.fight_ghast"])
            FightGeometry["description"]["identifier"] = "geometry.ghast"
            FightGeometry["bones"] = [
                Bone for Bone in FightGeometry["bones"] if Bone["name"] != "body_move"
            ]
            next(Bone for Bone in FightGeometry["bones"] if Bone["name"] == "body").pop("parent")
            assert FightGeometry == NativeGeometry
            WalkPosition = Exported["animation.arris_ghast.walk"]["bones"]["body"]["position"]
            assert WalkPosition["0.5"]["post"] == [-0.9, -6.75, 0]
        TotalAnimations += len(Exported)
    assert TotalAnimations == 86
    assert len(GeometryIdentifiers) == 7
    return TotalAnimations, len(GeometryIdentifiers)


def ActiveGameRoots():
    Config = ReadJson(PROJECT_ROOT / ".mcdev.json")
    Executable = Path(Config["game_executable_path"])
    GameRoot = Executable.parent
    return (
        GameRoot / "data" / "behavior_packs" / "vanilla",
        GameRoot / "data" / "resource_packs" / "vanilla",
    )


def ComponentOccurrences(EntityDocument):
    Entity = EntityDocument["minecraft:entity"]
    Result = {}
    for Components in [Entity.get("components", {})] + list(Entity.get("component_groups", {}).values()):
        for Name, Value in Components.items():
            Result.setdefault(Name, []).append(Value)
    return Result


def LegacyControllerMap(Description):
    Result = {}
    for Entry in Description.get("animation_controllers", []):
        Result.update(Entry)
    for Key, Value in Description.get("animations", {}).items():
        if isinstance(Value, str) and Value.startswith("controller.animation."):
            Result[Key] = Value
    return Result


def AssertCurrentVanillaBaseline():
    BehaviorRoot, ResourceRoot = ActiveGameRoots()
    StaticClasses = FindStaticClasses()
    CheckedComponents = 0
    for MobName, Config in MOBS.items():
        ClientPath = ResourceRoot / "entity" / (MobName + ".entity.json")
        Description = ReadJson(ClientPath)["minecraft:client_entity"]["description"]
        DeclaredAnimations = Description.get("animations", {})
        NativeAnimationMap = dict(
            (Key, Value) for Key, Value in DeclaredAnimations.items()
            if not (isinstance(Value, str) and Value.startswith("controller.animation."))
        )
        if MobName == "ghast":
            assert NativeAnimationMap.pop("scale") == "animation.ghast.scale"
        assert NativeAnimationMap == Config["native_animations"], MobName
        assert LegacyControllerMap(Description) == Config["native_controllers"], MobName

        EntityPath = BehaviorRoot / "entities" / (MobName + ".json")
        Behavior = ReadJsonWithComments(EntityPath)
        Occurrences = ComponentOccurrences(Behavior)
        _, EntityClass, Assignments = next(
            (Alias, ClassNode, Values)
            for EntityType, (Alias, ClassNode, Values) in StaticClasses.items()
            if EntityType == Config["entity"]
        )
        del EntityClass
        EntityTree = ast.parse((ENTITY_ROOT / (Config["class"] + ".py")).read_text(encoding="utf-8-sig"))
        EntityAssignments = ReadAssignments(FindNamedClass(EntityTree, Config["class"]))
        for MapName in ("NativeControlComponentMap", "NativeMeleeAttackComponentMap"):
            for ComponentName, ComponentValue in EntityAssignments[MapName].items():
                assert ComponentName in Occurrences, (MobName, ComponentName)
                assert ComponentValue in Occurrences[ComponentName], (MobName, ComponentName, ComponentValue)
                CheckedComponents += 1
        assert Assignments["geometry"] == Config["geometry"]
    assert CheckedComponents == 83
    return len(MOBS), CheckedComponents


def SnapshotProfileAccepts(MobName, Assignments, Components):
    Required = Assignments["NativeSnapshotRequiredComponents"]
    if not Components or not all(Name in Components for Name in Required):
        return False
    Profiles = Assignments.get("NativeSnapshotRequiredProfiles", ())
    if Profiles and not any(all(Name in Components for Name in Profile) for Profile in Profiles):
        return False
    for Marker, Names in Assignments.get("NativeSnapshotConditionalComponents", {}).items():
        if Marker in Components and not all(Name in Components for Name in Names):
            return False
    if MobName == "slime":
        VariantData = Components.get("minecraft:variant") or {}
        Variant = VariantData.get("value") if isinstance(VariantData, dict) else None
        if Variant not in (1, 2, 4):
            return False
        if Variant != 1 and "minecraft:area_attack" not in Components:
            return False
    if MobName == "ravager":
        if "minecraft:behavior.delayed_attack" not in Components:
            return False
        if "minecraft:is_stunned" in Components or "minecraft:behavior.knockback_roar" in Components:
            return False
    return True


def AssertSnapshotProfiles():
    BehaviorRoot, _ = ActiveGameRoots()
    LegalProfiles = {}
    InvalidProfiles = {}
    AssignmentsByMob = {}
    for MobName, Config in MOBS.items():
        EntityTree = ast.parse((ENTITY_ROOT / (Config["class"] + ".py")).read_text(encoding="utf-8-sig"))
        AssignmentsByMob[MobName] = ReadAssignments(FindNamedClass(EntityTree, Config["class"]))

    def LoadEntity(MobName):
        return ReadJsonWithComments(BehaviorRoot / "entities" / (MobName + ".json"))["minecraft:entity"]

    def Merge(Entity, GroupNames):
        Components = copy.deepcopy(Entity.get("components", {}))
        for GroupName in GroupNames:
            Components.update(copy.deepcopy(Entity["component_groups"][GroupName]))
        return Components

    Spider = LoadEntity("spider")
    LegalProfiles["spider"] = [
        Merge(Spider, (GroupName,))
        for GroupName in ("minecraft:spider_neutral", "minecraft:spider_hostile")
    ] + [
        Merge(Spider, (GroupName, "minecraft:spider_angry"))
        for GroupName in ("minecraft:spider_neutral", "minecraft:spider_hostile")
    ]
    InvalidProfiles["spider"] = [
        dict((Key, Value) for Key, Value in LegalProfiles["spider"][-1].items() if Key != "minecraft:behavior.melee_box_attack"),
        dict((Key, Value) for Key, Value in LegalProfiles["spider"][-1].items() if Key != "minecraft:behavior.leap_at_target"),
        dict((Key, Value) for Key, Value in LegalProfiles["spider"][-1].items() if Key != "minecraft:angry"),
    ]

    Blaze = LoadEntity("blaze")
    LegalProfiles["blaze"] = [
        Merge(Blaze, ("mode_switcher", "melee_mode")),
        Merge(Blaze, ("mode_switcher", "ranged_mode")),
    ]
    InvalidProfiles["blaze"] = [
        Merge(Blaze, ("mode_switcher",)),
        dict((Key, Value) for Key, Value in LegalProfiles["blaze"][0].items() if Key != "minecraft:behavior.melee_box_attack"),
        dict((Key, Value) for Key, Value in LegalProfiles["blaze"][1].items() if Key != "minecraft:behavior.ranged_attack"),
    ]
    BlazeMixedPartial = copy.deepcopy(LegalProfiles["blaze"][0])
    BlazeMixedPartial["minecraft:shooter"] = LegalProfiles["blaze"][1]["minecraft:shooter"]
    InvalidProfiles["blaze"].append(BlazeMixedPartial)

    Enderman = LoadEntity("enderman")
    LegalProfiles["enderman"] = [
        Merge(Enderman, (Mood, Riding))
        for Mood in ("minecraft:enderman_calm", "minecraft:enderman_angry")
        for Riding in ("minecraft:riding", "minecraft:not_riding")
    ]
    InvalidProfiles["enderman"] = [
        dict((Key, Value) for Key, Value in LegalProfiles["enderman"][2].items() if Key != "minecraft:behavior.melee_box_attack"),
        dict((Key, Value) for Key, Value in LegalProfiles["enderman"][2].items() if Key != "minecraft:angry"),
    ]

    Ghast = LoadEntity("ghast")
    LegalProfiles["ghast"] = [Merge(Ghast, ())]
    InvalidProfiles["ghast"] = [
        dict((Key, Value) for Key, Value in LegalProfiles["ghast"][0].items() if Key != "minecraft:behavior.ranged_attack"),
    ]

    Slime = LoadEntity("slime")
    LegalProfiles["slime"] = [
        Merge(Slime, (Size, Mood))
        for Size in ("minecraft:slime_small", "minecraft:slime_medium", "minecraft:slime_large")
        for Mood in ("minecraft:slime_calm", "minecraft:slime_aggressive")
    ]
    InvalidProfiles["slime"] = [
        dict((Key, Value) for Key, Value in LegalProfiles["slime"][-1].items() if Key != "minecraft:area_attack"),
    ]

    Ravager = LoadEntity("ravager")
    LegalProfiles["ravager"] = [
        Merge(Ravager, ("minecraft:hostile",)),
        Merge(Ravager, ("minecraft:hostile", "minecraft:raid_configuration")),
        Merge(Ravager, ("minecraft:hostile", "minecraft:celebrate")),
    ]
    InvalidProfiles["ravager"] = [
        Merge(Ravager, ("stunned",)),
        Merge(Ravager, ("roaring",)),
    ]

    LegalCount = 0
    InvalidCount = 0
    for MobName in MOBS:
        Assignments = AssignmentsByMob[MobName]
        for Components in LegalProfiles[MobName]:
            assert SnapshotProfileAccepts(MobName, Assignments, Components), MobName
            LegalCount += 1
        for Components in InvalidProfiles[MobName]:
            assert not SnapshotProfileAccepts(MobName, Assignments, Components), MobName
            InvalidCount += 1
        Representative = LegalProfiles[MobName][0]
        for RequiredName in Assignments["NativeSnapshotRequiredComponents"]:
            Partial = dict((Key, Value) for Key, Value in Representative.items() if Key != RequiredName)
            assert not SnapshotProfileAccepts(MobName, Assignments, Partial), (MobName, RequiredName)
            InvalidCount += 1
    return LegalCount, InvalidCount


def AssertLifecycleBase():
    Source = (ENTITY_ROOT / "BaseMob.py").read_text(encoding="utf-8-sig")
    Tree = ast.parse(Source)
    Classes = [Node for Node in Tree.body if isinstance(Node, ast.ClassDef) and Node.name == "SwordSoulMobEntity"]
    RuntimeClass = Classes[-1]
    Method = next(Node for Node in RuntimeClass.body if isinstance(Node, ast.FunctionDef) and Node.name == "sync_fight_render_state")
    MethodSource = ast.get_source_segment(Source, Method)
    assert "self.mode == MobCombatMode.FIGHT" in MethodSource
    assert "stateId != \"fight_none\"" not in MethodSource

    VanillaPath = ENTITY_ROOT / "VanillaFightMob.py"
    VanillaSource = VanillaPath.read_text(encoding="utf-8-sig")
    VanillaTree = ast.parse(VanillaSource)
    VanillaClass = FindNamedClass(VanillaTree, "VanillaFightMobEntity")

    class FakeMode(object):
        NATIVE = "native"
        FIGHT = "fight"

    class FakeBase(object):
        NativeControlComponentMap = {}
        NativeMeleeAttackComponentMap = {}
        ReactionResultStateIds = ()

        def __init__(self, EntityId):
            self.entityId = EntityId
            self.hard_enabled = True
            self.mode = FakeMode.NATIVE
            self.soft_enabled = False
            self._destroyed = False
            self.removed = []
            self.added = []
            self.fail_remove = None
            self.fail_add = None
            self.executed = []
            self.pending_fight_request = None
            self.commands = []
            self.rendered = []

        def get_native_control_component_map(self):
            return self.NativeControlComponentMap

        def get_native_melee_attack_component_map(self):
            return self.NativeMeleeAttackComponentMap

        def remove_actor_component(self, Name):
            self.removed.append(Name)
            return Name != self.fail_remove

        def add_actor_component(self, Name, Value):
            self.added.append((Name, copy.deepcopy(Value)))
            return Name != self.fail_add

        def set_soft_switch(self, Enabled):
            Target = FakeMode.FIGHT if Enabled and self.hard_enabled else FakeMode.NATIVE
            self.soft_enabled = Target == FakeMode.FIGHT
            if self.mode == Target:
                return True
            Old = self.mode
            self.mode = Target
            self.render_molang("query.mod.fight", 1.0 if Target == FakeMode.FIGHT else 0.0)
            self.on_combat_mode_changed(Old, Target)
            return True

        def enter_fight_mode(self):
            return self.set_soft_switch(True)

        def set_hard_switch(self, Enabled):
            self.hard_enabled = bool(Enabled)
            if not self.hard_enabled:
                self.set_soft_switch(False)
            return True

        def tick(self, TickIndex=0, Alive=None):
            del TickIndex, Alive
            return self.hard_enabled

        def execute_fight_state(self, StateId, Request=None, Force=False):
            self.executed.append((StateId, Request, Force))
            return True

        def request_fight_state(self, StateId, Request=None, Force=False, SoftDuration=2.0):
            self.pending_fight_request = (StateId, Request, Force, SoftDuration)
            return True

        def input_command(self, Command, Payload=None, Duration=None):
            self.commands.append((Command, Payload, Duration))
            return True

        def render_molang(self, QueryId, Value):
            self.rendered.append((QueryId, Value))
            return True

        def destroy(self):
            if self._destroyed:
                return False
            self._destroyed = True
            return True

    class FakeEventComponent(object):
        def __init__(self, Components):
            self.Components = Components

        def GetComponents(self):
            return self.Components

    class FakeServerComp(object):
        Components = {}

        @classmethod
        def CreateEntityEvent(cls, EntityId):
            del EntityId
            if cls.Components is None:
                return None
            return FakeEventComponent(cls.Components)

    Module = ast.Module(body=[VanillaClass], type_ignores=[])
    ast.fix_missing_locations(Module)
    Namespace = {
        "copy": copy,
        "SwordSoulMobEntity": FakeBase,
        "MobCombatMode": FakeMode,
        "ServerComp": FakeServerComp,
    }
    exec(compile(Module, str(VanillaPath), "exec"), Namespace)
    VanillaClassValue = Namespace["VanillaFightMobEntity"]

    class Probe(VanillaClassValue):
        NativeControlComponentMap = {"control_active": {"value": 1}, "control_inactive": {"value": 2}}
        NativeMeleeAttackComponentMap = {"attack_active": {"damage": 3}, "attack_inactive": {"damage": 4}}

    CompleteComponents = {
        "minecraft:type_family": {"family": ["mob"]},
        "minecraft:health": {"value": 20, "max": 20},
        "minecraft:movement": {"value": 0.3},
        "minecraft:attack": {"damage": 2},
        "control_active": {"value": 11},
        "attack_active": {"damage": 33},
        "unrelated": {"keep": True},
    }
    FakeServerComp.Components = copy.deepcopy(CompleteComponents)
    ProbeValue = Probe("entity")
    assert ProbeValue.set_soft_switch(True) is True
    assert ProbeValue.mode == FakeMode.FIGHT
    assert set(ProbeValue.removed) == {
        "control_active", "control_inactive", "attack_active", "attack_inactive",
    }
    ProbeValue.set_native_control_enabled(True)
    ProbeValue.set_native_melee_attack_enabled(True)
    assert ProbeValue.added == []
    assert ProbeValue.set_soft_switch(False) is True
    assert ProbeValue.mode == FakeMode.NATIVE
    assert ProbeValue.added == [
        ("control_active", {"value": 11}),
        ("attack_active", {"damage": 33}),
    ]

    FakeServerComp.Components = None
    MissingSnapshot = Probe("missing")
    assert MissingSnapshot.set_soft_switch(True) is False
    assert MissingSnapshot.mode == FakeMode.NATIVE
    assert MissingSnapshot.execute_fight_state("fight_attack_first") is False
    assert MissingSnapshot.request_fight_state("fight_attack_first") is False
    assert MissingSnapshot.input_command("attack") is False
    assert MissingSnapshot.executed == []
    assert MissingSnapshot.pending_fight_request is None
    assert MissingSnapshot.commands == []

    FakeServerComp.Components = {}
    PartialSnapshot = Probe("partial")
    assert PartialSnapshot.set_soft_switch(True) is False
    assert PartialSnapshot.removed == []

    FakeServerComp.Components = copy.deepcopy(CompleteComponents)
    FailedRemoval = Probe("failed")
    FailedRemoval.fail_remove = "attack_active"
    assert FailedRemoval.set_soft_switch(True) is False
    assert FailedRemoval.mode == FakeMode.NATIVE
    assert ("control_active", {"value": 11}) in FailedRemoval.added
    assert ("attack_active", {"damage": 33}) in FailedRemoval.added

    FakeServerComp.Components = copy.deepcopy(CompleteComponents)
    FailedRestore = Probe("restore")
    assert FailedRestore.set_soft_switch(True) is True
    FailedRestore.fail_add = "attack_active"
    assert FailedRestore.set_soft_switch(False) is False
    assert FailedRestore.mode == FakeMode.NATIVE
    assert FailedRestore.NativeComponentSnapshotReady is True
    assert FailedRestore.NativeControlSuppressed is True
    assert FailedRestore.NativeAttackSuppressed is True
    assert set(FailedRestore.NativeControlRestoreMap) == {"control_active"}
    assert set(FailedRestore.NativeAttackRestoreMap) == {"attack_active"}
    RemoveCount = len(FailedRestore.removed)
    assert FailedRestore.set_soft_switch(True) is False
    assert FailedRestore.mode == FakeMode.NATIVE
    assert len(FailedRestore.removed) == RemoveCount
    FailedRestore.fail_add = None
    assert FailedRestore.set_soft_switch(False) is True
    assert FailedRestore.NativeComponentSnapshotReady is False
    assert FailedRestore.set_soft_switch(True) is True

    FakeServerComp.Components = copy.deepcopy(CompleteComponents)
    HardSwitchProbe = Probe("hard_switch")
    assert HardSwitchProbe.set_soft_switch(True) is True
    HardSwitchProbe.fail_add = "attack_active"
    assert HardSwitchProbe.set_hard_switch(False) is False
    assert HardSwitchProbe.mode == FakeMode.NATIVE
    assert HardSwitchProbe.NativeComponentSnapshotReady is True
    assert HardSwitchProbe.set_hard_switch(True) is False
    assert HardSwitchProbe.hard_enabled is False
    HardSwitchProbe.fail_add = None
    assert HardSwitchProbe.tick(1, True) is True
    assert HardSwitchProbe.NativeComponentSnapshotReady is False

    FakeServerComp.Components = copy.deepcopy(CompleteComponents)
    DestroyProbe = Probe("destroy")
    assert DestroyProbe.set_soft_switch(True) is True
    assert DestroyProbe.destroy() is True
    assert DestroyProbe._destroyed is True
    assert DestroyProbe.mode == FakeMode.NATIVE
    assert DestroyProbe.rendered[-1] == ("query.mod.fight", 0.0)
    return 8


def AssertRuntimeTransactionGates():
    ControllerPath = SCRIPT_ROOT / "Combat" / "FightController.py"
    ControllerSource = ControllerPath.read_text(encoding="utf-8-sig")
    ControllerTree = ast.parse(ControllerSource)
    ControllerClass = FindNamedClass(ControllerTree, "MobFightController")
    SetState = next(
        Node for Node in ControllerClass.body
        if isinstance(Node, ast.FunctionDef) and Node.name == "set_state"
    )
    SetStateSource = ast.get_source_segment(ControllerSource, SetState)
    assert "not self.mob.enter_fight_mode()" in SetStateSource
    assert SetStateSource.rfind("enter_fight_mode") < SetStateSource.rfind("_translate_to_state")
    OnFightState = next(
        Node for Node in ControllerClass.body
        if isinstance(Node, ast.FunctionDef) and Node.name == "OnFightState"
    )
    OnFightStateSource = ast.get_source_segment(ControllerSource, OnFightState)
    assert "not self.mob.enter_fight_mode()" in OnFightStateSource
    assert OnFightStateSource.index("enter_fight_mode") < OnFightStateSource.index("CancelControl")

    VanillaSource = (ENTITY_ROOT / "VanillaFightMob.py").read_text(encoding="utf-8-sig")
    VanillaTree = ast.parse(VanillaSource)
    VanillaClass = FindNamedClass(VanillaTree, "VanillaFightMobEntity")
    VanillaAssignments = ReadAssignments(VanillaClass)
    assert set(VanillaAssignments["NativeSnapshotRequiredComponents"]) == {
        "minecraft:type_family", "minecraft:health", "minecraft:movement",
    }
    assert VanillaAssignments["NativeSnapshotRequiredProfiles"] == (
        ("minecraft:attack",),
        ("minecraft:shooter",),
    )
    SetSoftSwitch = next(
        Node for Node in VanillaClass.body
        if isinstance(Node, ast.FunctionDef) and Node.name == "set_soft_switch"
    )
    SetSoftSwitchSource = ast.get_source_segment(VanillaSource, SetSoftSwitch)
    assert SetSoftSwitchSource.index("set_native_control_enabled(False)") < SetSoftSwitchSource.index(
        "SwordSoulMobEntity.set_soft_switch"
    )

    ServerPath = SCRIPT_ROOT / "SwordSoulMobServer.py"
    ServerSource = ServerPath.read_text(encoding="utf-8-sig")
    ServerTree = ast.parse(ServerSource)
    ServerClass = FindNamedClass(ServerTree, "MobCombatSystem")
    NativeGuard = next(
        Node for Node in ServerClass.body
        if isinstance(Node, ast.FunctionDef) and Node.name == "try_native_attack_safety_reaction"
    )
    NativeGuardSource = ast.get_source_segment(ServerSource, NativeGuard)
    assert 'args["damage"]' not in NativeGuardSource
    assert 'args["knock"]' not in NativeGuardSource
    assert "return bool(result)" in NativeGuardSource
    EnterGuard = next(
        Node for Node in ServerClass.body
        if isinstance(Node, ast.FunctionDef) and Node.name == "enter_native_attack_guard_state"
    )
    EnterGuardSource = ast.get_source_segment(ServerSource, EnterGuard)
    assert "ResolveReactionState" in EnterGuardSource
    assert "TryReactionState" in EnterGuardSource
    RemoveMob = next(
        Node for Node in ServerClass.body
        if isinstance(Node, ast.FunctionDef) and Node.name == "remove_mob"
    )
    RemoveMobSource = ast.get_source_segment(ServerSource, RemoveMob)
    assert "destroyResult is False" in RemoveMobSource
    SetHardSwitchCall = next(
        Node for Node in ServerClass.body
        if isinstance(Node, ast.FunctionDef) and Node.name == "SetMobCombatHardSwitch"
    )
    SetHardSwitchCallSource = ast.get_source_segment(ServerSource, SetHardSwitchCall)
    assert "result = mob.set_hard_switch(enabled)" in SetHardSwitchCallSource
    assert "if result is False" in SetHardSwitchCallSource
    assert "bool(mob.hard_enabled)" in SetHardSwitchCallSource
    RepairUnregistered = next(
        Node for Node in ServerClass.body
        if isinstance(Node, ast.FunctionDef) and Node.name == "repair_unregistered_entity"
    )
    RepairUnregisteredSource = ast.get_source_segment(ServerSource, RepairUnregistered)
    assert "GetEngineTypeStr" in RepairUnregisteredSource
    assert "currentIdentifier == mob.identifier" in RepairUnregisteredSource
    assert "mob.destroy()" in RepairUnregisteredSource
    DestroyRuntime = next(
        Node for Node in ServerClass.body
        if isinstance(Node, ast.FunctionDef) and Node.name == "destroy_runtime_without_state_reset"
    )
    DestroyRuntimeSource = ast.get_source_segment(ServerSource, DestroyRuntime)
    assert 'render_molang("query.mod.fight", 0.0)' in DestroyRuntimeSource
    assert "SwordSoulMobEntity.destroy(mob)" in DestroyRuntimeSource

    MethodModule = ast.Module(body=[copy.deepcopy(EnterGuard)], type_ignores=[])
    ast.fix_missing_locations(MethodModule)
    Namespace = {}
    exec(compile(MethodModule, str(ServerPath), "exec"), Namespace)
    EnterGuardMethod = Namespace["enter_native_attack_guard_state"]

    class GuardControl(object):
        def __init__(self):
            self.AttackState = "old_attack"
            self.ReadyAttack = True
            self.Control_Defense = True
            self.DefenseState = True
            self.Control_Dodge = True
            self.DodgeState = True
            self.DodgeType = "none"
            self.DodgeLevel = 0
            self.DefenseType = "none"
            self.SwordSoulValue = 10.0
            self.SwordSoulValue_MAX = 100.0
            self.DodgeNeedPhysical = 20.0
            self.DefenseNeedPhysical = 10.0
            self.PhysicalAllowed = True
            self.PhysicalChecks = []

        def CheckPhysical(self, Cost):
            self.PhysicalChecks.append(Cost)
            return self.PhysicalAllowed

    class GuardMob(object):
        def __init__(self):
            self.command_translator = GuardControl()

    class GuardController(object):
        def __init__(self):
            self.mob = GuardMob()
            self.ResolvedStateId = ""
            self.Result = False
            self.TryCalls = []
            self.PerfectDefenseUpdates = []

        def ResolveReactionState(self, StateId):
            del StateId
            return self.ResolvedStateId

        def TryReactionState(self, Requested, Resolved, Changes, Request):
            self.TryCalls.append((Requested, Resolved, dict(Changes), dict(Request)))
            return self.Result

        def UpdatePerfectDefenseState(self, State):
            self.PerfectDefenseUpdates.append(State)

    Guard = GuardController()
    Guard.ResolvedStateId = "fight_hit_light"
    assert EnterGuardMethod(object(), Guard, "fight_common_defense", "source") is False
    assert Guard.TryCalls == []

    Guard.ResolvedStateId = "fight_dodge_left"
    Guard.mob.command_translator.PhysicalAllowed = False
    assert EnterGuardMethod(object(), Guard, "fight_dodge_left", "source") is False
    assert Guard.TryCalls == []
    assert Guard.mob.command_translator.PhysicalChecks == [20.0]
    assert Guard.mob.command_translator.AttackState == "old_attack"
    Guard.mob.command_translator.PhysicalAllowed = True
    assert EnterGuardMethod(object(), Guard, "fight_dodge_left", "source") is False
    Guard.Result = True
    assert EnterGuardMethod(object(), Guard, "fight_dodge_left", "source") is True
    assert Guard.TryCalls[-1][2]["DodgeType"] == "common"

    Guard.ResolvedStateId = "fight_common_defense"
    Guard.Result = False
    assert EnterGuardMethod(object(), Guard, "fight_common_defense", "source") is False
    assert Guard.mob.command_translator.PhysicalChecks[-1] == 10.0

    PhysicalCheckCount = len(Guard.mob.command_translator.PhysicalChecks)
    Guard.Result = True
    Guard.ResolvedStateId = "fight_perfect_defense"
    assert EnterGuardMethod(object(), Guard, "fight_perfect_defense", "source") is True
    assert Guard.PerfectDefenseUpdates == [True]
    Guard.ResolvedStateId = "fight_dodge_left_perfect"
    assert EnterGuardMethod(object(), Guard, "fight_dodge_left_perfect", "source") is True
    assert Guard.mob.command_translator.SwordSoulValue == 60.0
    assert len(Guard.mob.command_translator.PhysicalChecks) == PhysicalCheckCount

    class FakeEngineType(object):
        CurrentIdentifier = ""

        @classmethod
        def GetEngineTypeStr(cls, EntityId):
            del EntityId
            return cls.CurrentIdentifier

    class FakeEntityApi(object):
        EngineType = FakeEngineType

    class FakeServerApi(object):
        Entity = FakeEntityApi

    RepairModule = ast.Module(body=[copy.deepcopy(RepairUnregistered)], type_ignores=[])
    ast.fix_missing_locations(RepairModule)
    RepairNamespace = {"ServerApi": FakeServerApi}
    exec(compile(RepairModule, str(ServerPath), "exec"), RepairNamespace)
    RepairMethod = RepairNamespace["repair_unregistered_entity"]

    class RepairMob(object):
        identifier = "minecraft:spider"

        def __init__(self, Result):
            self.Result = Result
            self._destroyed = False
            self.DestroyCalls = 0

        def destroy(self):
            self.DestroyCalls += 1
            if self.Result:
                self._destroyed = True
            return self.Result

    class RepairSystem(object):
        def __init__(self, Mob):
            self.mob_map = {"entity": Mob}
            self.hard_switch_map = {"entity": True}
            self.CleanupCalls = []

        def destroy_runtime_without_state_reset(self, Mob):
            self.CleanupCalls.append(Mob)

    FailedRepairMob = RepairMob(False)
    FailedRepair = RepairSystem(FailedRepairMob)
    FakeEngineType.CurrentIdentifier = "minecraft:spider"
    assert RepairMethod(FailedRepair, "entity") is False
    assert FailedRepairMob.DestroyCalls == 1
    assert "entity" in FailedRepair.mob_map

    FailedRepairMob.Result = True
    assert RepairMethod(FailedRepair, "entity") is True
    assert "entity" not in FailedRepair.mob_map
    assert "entity" not in FailedRepair.hard_switch_map

    DeferredRepairMob = RepairMob(True)
    DeferredRepair = RepairSystem(DeferredRepairMob)
    FakeEngineType.CurrentIdentifier = ""
    assert RepairMethod(DeferredRepair, "entity") is False
    assert DeferredRepairMob.DestroyCalls == 0
    assert "entity" in DeferredRepair.mob_map

    TransformedMob = RepairMob(True)
    TransformedRepair = RepairSystem(TransformedMob)
    FakeEngineType.CurrentIdentifier = "minecraft:cow"
    assert RepairMethod(TransformedRepair, "entity") is True
    assert TransformedMob.DestroyCalls == 0
    assert TransformedRepair.CleanupCalls == [TransformedMob]
    return 9


def Main():
    AnimationDocuments, GeometryDocuments = FindResourceDocuments()
    EntityCount, StateCount = AssertEntityModules()
    AliasCount, RegisteredAnimationCount, CaseCount = AssertStaticAndControllers(AnimationDocuments)
    AnimationCount, GeometryCount = AssertAnimationTimingAndGeometry(AnimationDocuments, GeometryDocuments)
    VanillaCount, ComponentCount = AssertCurrentVanillaBaseline()
    LegalProfileCount, InvalidProfileCount = AssertSnapshotProfiles()
    LifecycleCases = AssertLifecycleBase()
    TransactionCases = AssertRuntimeTransactionGates()
    print(
        "collection mob deployment checks passed: entities=%d states=%d aliases=%d "
        "animations=%d registered=%d geometries=%d controller_cases=%d "
        "vanilla_chains=%d components=%d profiles=%d/%d lifecycle_cases=%d transaction_cases=%d"
        % (
            EntityCount, StateCount, AliasCount, AnimationCount,
            RegisteredAnimationCount, GeometryCount, CaseCount,
            VanillaCount, ComponentCount, LegalProfileCount, InvalidProfileCount,
            LifecycleCases, TransactionCases,
        )
    )


if __name__ == "__main__":
    Main()
