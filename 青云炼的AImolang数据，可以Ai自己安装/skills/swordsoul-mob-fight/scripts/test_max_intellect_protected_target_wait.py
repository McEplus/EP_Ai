# coding=utf-8
"""最高智力目标保护窗口观望与闪避决策回归。"""

import ast
import math
import runpy
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[4]
MOB_ROOT = PROJECT_ROOT / "src" / "SwordSoul_NewERA_B" / "SwordSoulMobFightScripts"
CORE_PATH = MOB_ROOT / "AI" / "Core.py"
INTELLECT_PATH = MOB_ROOT / "AI" / "Intellect.py"
SENSE_PATH = MOB_ROOT / "AI" / "Sense.py"
FIGHT_CONTROLLER_PATH = MOB_ROOT / "Combat" / "FightController.py"
ENTITIES_ROOT = MOB_ROOT / "Entities"


def ReadClass(PathValue, ClassName):
    Tree = ast.parse(PathValue.read_text(encoding="utf-8-sig"))
    return next(Node for Node in Tree.body if isinstance(Node, ast.ClassDef) and Node.name == ClassName)


def ReadMethod(PathValue, ClassName, MethodName):
    ClassNode = ReadClass(PathValue, ClassName)
    return next(
        Node for Node in ClassNode.body
        if isinstance(Node, ast.FunctionDef) and Node.name == MethodName
    )


def BuildHarness(Name, PathValue, ClassName, MethodNames, Namespace=None):
    Methods = [ReadMethod(PathValue, ClassName, MethodName) for MethodName in MethodNames]
    ClassNode = ast.ClassDef(
        name=Name,
        bases=[ast.Name(id="object", ctx=ast.Load())],
        keywords=[],
        body=Methods,
        decorator_list=[],
    )
    ModuleNode = ast.Module(body=[ClassNode], type_ignores=[])
    ast.fix_missing_locations(ModuleNode)
    Result = dict(Namespace or {})
    exec(compile(ModuleNode, str(PathValue), "exec"), Result)
    return Result[Name]


class ValueObject(object):
    def __init__(self, **Values):
        self.__dict__.update(Values)


class FakeTags(object):
    DEFENSE = "defense"
    DODGE = "dodge"
    ADVANCE = "advance"
    DODGE_TO_DEFENSE = "dodge_to_defense"


class FakeDecision(object):
    def __init__(self, Skill, Score, Reason):
        self.skill = Skill
        self.score = Score
        self.reason = Reason


class FakeSkill(object):
    def __init__(self, SkillId, Tags, StateId="", Direction=""):
        self.skillId = SkillId
        self.tags = set(Tags)
        self.stateId = StateId
        self.payload = {"direction": Direction}
        self.command = "dodge"
        self.duration = 0.15

    def make_payload(self):
        return dict(self.payload)


class FakeController(object):
    def __init__(self):
        self.InFightState = False
        self.FinishState = True
        self.StateType = "none"
        self.StateId = "fight_none"
        self.controlCalls = []
        self.meleeCalls = []

    def SetNativeControlState(self, Enabled):
        self.controlCalls.append(bool(Enabled))
        return True

    def SetNativeMeleeAttackState(self, Enabled):
        self.meleeCalls.append(bool(Enabled))
        return True

    def get_state_type(self):
        return self.StateType

    def get_state_id(self):
        return self.StateId


class FakeMob(object):
    def __init__(self, Controller):
        self.fight_controller = Controller
        self.entityId = "max-intellect-mob"
        self.sense = ValueObject(selfSense=ValueObject(lastAttackTime=0.0))
        self.inputCalls = []
        self.SecondStates = {
            "fight_dodge_back_second",
            "fight_dodge_left_second",
            "fight_dodge_right_second",
        }

    def HasFightState(self, StateId):
        return StateId in self.SecondStates

    def input_command(self, Command, Payload, Duration):
        self.inputCalls.append((Command, dict(Payload), Duration))
        return True


def SafeFloat(Value, Default=0.0):
    try:
        return float(Value)
    except (TypeError, ValueError):
        return float(Default)


def Main():
    # Codex 2026-08-10: 保护窗口规避是 Max 档位硬能力，实体覆写不得降级或越级开启。
    IntellectModule = runpy.run_path(str(INTELLECT_PATH))
    ResolveIntellect = IntellectModule["resolve_intellect"]
    for Tier in ("low", "mid", "high"):
        Params = ResolveIntellect(ValueObject(aiIntellect=Tier, aiIntellectParams=None))
        assert not Params.tacticProtectedTargetWait, Tier
    MaxParams = ResolveIntellect(ValueObject(aiIntellect="max", aiIntellectParams=None))
    assert MaxParams.tacticProtectedTargetWait
    MaxOverride = ResolveIntellect(ValueObject(
        aiIntellect="max",
        aiIntellectParams={"tacticProtectedTargetWait": False},
    ))
    assert MaxOverride.tacticProtectedTargetWait
    HighOverride = ResolveIntellect(ValueObject(
        aiIntellect="high",
        aiIntellectParams={"tacticProtectedTargetWait": True},
    ))
    assert not HighOverride.tacticProtectedTargetWait

    # 目前直接使用或继承 Max 的实体都经过同一 MobAICore，不得再派生生物专属决策实现。
    EntityClasses = {}
    for EntityPath in ENTITIES_ROOT.glob("*Mob.py"):
        for Node in ast.parse(EntityPath.read_text(encoding="utf-8-sig")).body:
            if not isinstance(Node, ast.ClassDef):
                continue
            Tier = None
            for Item in Node.body:
                if not isinstance(Item, ast.Assign) or len(Item.targets) != 1:
                    continue
                if isinstance(Item.targets[0], ast.Name) and Item.targets[0].id == "aiIntellect":
                    Tier = ast.literal_eval(Item.value)
            Bases = [Base.id for Base in Node.bases if isinstance(Base, ast.Name)]
            EntityClasses[Node.name] = {"tier": Tier, "bases": Bases, "node": Node}

    def ResolveEntityTier(ClassName, Seen=None):
        Seen = set(Seen or ())
        if ClassName in Seen or ClassName not in EntityClasses:
            return None
        Seen.add(ClassName)
        Entry = EntityClasses[ClassName]
        if Entry["tier"] is not None:
            return Entry["tier"]
        for BaseName in Entry["bases"]:
            Tier = ResolveEntityTier(BaseName, Seen)
            if Tier is not None:
                return Tier
        return None

    MaxEntityClasses = {
        ClassName for ClassName in EntityClasses
        if ResolveEntityTier(ClassName) == "max"
    }
    assert {"QingYunMob", "FlowerMob", "TrainingDummyMob", "MaidMob"} <= MaxEntityClasses
    assert all(
        not any(
            isinstance(Item, ast.FunctionDef)
            and Item.name == "_try_protected_target_wait_decision"
            for Item in EntityClasses[ClassName]["node"].body
        )
        for ClassName in MaxEntityClasses
    )

    TacticsHarness = BuildHarness(
        "TacticsHarness",
        CORE_PATH,
        "CombatTactics",
        (
            "target_has_protected_skill_window",
            "spatial_escape_safe_radius",
            "predict_dodge_end_distance",
            "dodge_direction",
        ),
        {"math": math},
    )
    TacticsHarness.SPATIAL_ESCAPE_SAFETY_BUFFER = 0.55
    TacticsHarness.SPATIAL_ESCAPE_BACK_DISTANCE = 2.2
    TacticsHarness.SPATIAL_ESCAPE_LATERAL_DISTANCE = 2.0
    for MethodName in ("spatial_escape_safe_radius", "predict_dodge_end_distance"):
        getattr(TacticsHarness, MethodName).__globals__["CombatTactics"] = TacticsHarness
    assert TacticsHarness.target_has_protected_skill_window({"godState": True})
    assert TacticsHarness.target_has_protected_skill_window({
        "fightStateId": "fight_skill_black_hole",
        "superArmor": 3.0,
    })
    assert TacticsHarness.target_has_protected_skill_window({
        "fightStateId": "fight_attack_super_skill",
        "superArmor": 1.0,
    })
    assert not TacticsHarness.target_has_protected_skill_window({
        "fightStateId": "fight_skill_black_hole",
        "superArmor": 0.0,
    })
    assert not TacticsHarness.target_has_protected_skill_window({
        "fightStateId": "fight_attack_first",
        "superArmor": 4.0,
    })

    class FakeTactics(TacticsHarness):
        DodgeNow = False
        GuardNow = False
        SpatialThreat = None

        @classmethod
        def target_can_dodge_now(cls, Sense, TargetInfo):
            return cls.DodgeNow

        @classmethod
        def target_can_guard_now(cls, Sense, TargetInfo):
            return cls.GuardNow

        @classmethod
        def target_remaining_spatial_threat(cls, Sense, TargetInfo):
            return cls.SpatialThreat

        @staticmethod
        def is_result_only_defense_skill(Skill):
            return False

        @staticmethod
        def should_lock_skill_commitment(Mob, Sense):
            return False

    CoreHarness = BuildHarness(
        "CoreHarness",
        CORE_PATH,
        "MobAICore",
        (
            "_sync_protected_target_wait",
            "_reset_spatial_escape_plan",
            "_sync_spatial_escape_plan",
            "_pick_spatial_escape_skill",
            "_can_chain_spatial_escape",
            "_remember_spatial_escape_step",
            "_try_protected_target_wait_decision",
            "_filter_current_reaction_skills",
            "_pick_emergency_skill",
            "_emergency_dodge_order",
            "execute_decision",
        ),
        {
            "CombatTactics": FakeTactics,
            "AISkillTag": FakeTags,
            "AIDecision": FakeDecision,
            "time": __import__("time"),
            "mob_trace": lambda *Args: None,
        },
    )
    Controller = FakeController()
    Core = CoreHarness()
    Core.mob = FakeMob(Controller)
    Core.intellect = ValueObject(tacticProtectedTargetWait=True)
    Core.protectedTargetWaitActive = False
    Core.lastLateralDodgeDirection = ""
    Core._reset_spatial_escape_plan()
    TargetInfo = {
        "targetId": "protected-skill-target",
        "fightStateId": "fight_skill_black_hole",
        "superArmor": 3.0,
        "godState": False,
    }
    Core.utilityEvaluator = ValueObject(
        targetReader=ValueObject(read=lambda Sense: ("charge_attack", TargetInfo)),
    )
    Sense = ValueObject(rangeSense=ValueObject(targetHorizontalDistance=2.0, targetAngle=0.0))
    Skills = [
        FakeSkill("common_attack", {"attack"}),
        FakeSkill("dodge_forward", {FakeTags.DODGE, FakeTags.ADVANCE}, Direction="forward"),
        FakeSkill("dodge_back", {FakeTags.DODGE}, Direction="back"),
        FakeSkill("dodge_left", {FakeTags.DODGE}, Direction="left"),
        FakeSkill("dodge_right", {FakeTags.DODGE}, Direction="right"),
    ]

    # 没有临近命中威胁时只等待，不为“看起来危险”而空闪。
    FakeTactics.DodgeNow = False
    Decision = Core._try_protected_target_wait_decision(Sense, Skills)
    assert Decision.skill is None
    assert Decision.reason == "protected_target_wait"
    assert Core.protectedTargetWaitActive
    assert Controller.controlCalls[-1] is False
    assert Controller.meleeCalls[-1] is False

    # 威胁窗口成立时选侧/后闪，禁止选择带 ADVANCE 的前闪。
    FakeTactics.DodgeNow = True
    Decision = Core._try_protected_target_wait_decision(Sense, Skills)
    assert Decision.skill.skillId == "dodge_left"
    assert FakeTags.ADVANCE not in Decision.skill.tags
    assert Decision.reason == "protected_target_threat_dodge"

    # 保护结束后立即退出观望并恢复追击/近战，后续决策树可在同一轮继续运行。
    TargetInfo.update({"fightStateId": "fight_none", "superArmor": 0.0})
    assert Core._try_protected_target_wait_decision(Sense, Skills) is None
    assert not Core.protectedTargetWaitActive
    assert Controller.controlCalls[-1] is True
    assert Controller.meleeCalls[-1] is True

    # 自身仍在招式中时不提前恢复原生组件，交给状态退出流程统一处理。
    TargetInfo.update({"godState": True})
    Core._try_protected_target_wait_decision(Sense, Skills)
    BeforeControlCount = len(Controller.controlCalls)
    BeforeMeleeCount = len(Controller.meleeCalls)
    Controller.InFightState = True
    TargetInfo.update({"godState": False})
    assert Core._try_protected_target_wait_decision(Sense, Skills) is None
    assert len(Controller.controlCalls) == BeforeControlCount
    assert len(Controller.meleeCalls) == BeforeMeleeCount

    # Codex 2026-08-10: 共享威胁画像必须把多段技能的正面段与延迟 360 度段分开。
    ProfileHarness = BuildHarness(
        "ProfileHarness",
        SENSE_PATH,
        "SkillRangeProfile",
        (
            "__init__",
            "apply_state_records",
            "remaining_attack_stages",
            "_sum_forward_motion_before",
            "_sum_forward_motion_between",
            "_estimate_motion_forward_distance",
            "apply_attack_data",
        ),
        {"math": math, "_safe_float": SafeFloat},
    )
    ProfileHarness.apply_state_records.__globals__["SkillRangeProfile"] = ProfileHarness
    Profile = ProfileHarness("fight_attack_execute")
    assert Profile.apply_state_records(
        [
            {"time": 0.25, "data": {"range": 3.2, "radians": 180, "high": 1.0, "offset": (0, 1, -0.2)}},
            {"time": 1.88, "data": {"range": 2.0, "radians": 360, "high": 20.0, "offset": (0, 0, -0.2)}},
        ],
        [{"time": 1.8072, "direction": (0, 0, 1), "power": 0.0192}],
    )
    assert [Stage["fullCircle"] for Stage in Profile.attackStages] == [False, True]
    RemainingStages = Profile.remaining_attack_stages(0.4, 0.12, True)
    assert len(RemainingStages) == 1
    assert abs(RemainingStages[0]["time"] - 1.88) < 0.0001
    assert abs(RemainingStages[0]["threatRange"] - 3.0192) < 0.0001
    assert Profile.remaining_attack_stages(2.01, 0.12, True) == []

    # Codex 2026-08-10: Mob 运行状态必须在 onStart 收集完成后，把相同的 AIRangeProfile 契约同步给 SWS 状态。
    class FakeBridge(object):
        Calls = []

        @classmethod
        def update_state(cls, EntityId, StateType, Value):
            cls.Calls.append((EntityId, StateType, dict(Value)))
            return True

    SyncHarness = BuildHarness(
        "SyncHarness",
        FIGHT_CONTROLLER_PATH,
        "MobFightController",
        ("_sync_ai_range_profile",),
        {"SWSFightBridge": FakeBridge},
    )
    SyncController = SyncHarness()
    SyncController.mob = ValueObject(entityId="protected-skill-target", WeaponType="empty")
    SyncState = ValueObject(
        StateId="fight_attack_execute",
        WeaponType="empty",
        AIAttackRecords=list(Profile.attackStages),
        AIMotionRecords=[{"time": 1.8072, "direction": (0, 0, 1), "power": 0.0192}],
        AttackData={},
        AIRangeHint=None,
    )
    assert SyncController._sync_ai_range_profile(SyncState)
    assert FakeBridge.Calls[-1][0:2] == ("protected-skill-target", "AIRangeProfile")
    assert FakeBridge.Calls[-1][2]["stateId"] == "fight_attack_execute"
    assert len(FakeBridge.Calls[-1][2]["attack_records"]) == 2
    RunStateNode = ReadMethod(FIGHT_CONTROLLER_PATH, "MobFightController", "RunFightState")
    OnStartLine = min(
        Node.lineno for Node in ast.walk(RunStateNode)
        if isinstance(Node, ast.Call) and isinstance(Node.func, ast.Attribute) and Node.func.attr == "onStart"
    )
    SyncLine = min(
        Node.lineno for Node in ast.walk(RunStateNode)
        if isinstance(Node, ast.Call) and isinstance(Node.func, ast.Attribute) and Node.func.attr == "_sync_ai_range_profile"
    )
    assert SyncLine > OnStartLine

    # Codex 2026-08-10: 面向目标且仍在安全半径内时，后闪落点比侧闪更远，必须优先后闪。
    TargetInfo.update({
        "fightStateId": "fight_attack_execute",
        "superArmor": 3.0,
        "godState": True,
    })
    Controller.InFightState = False
    Controller.StateType = "none"
    Controller.StateId = "fight_none"
    Controller.FinishState = True
    Sense.rangeSense.targetHorizontalDistance = 2.0
    Sense.rangeSense.targetAngle = 0.0
    FakeTactics.SpatialThreat = {"threatRange": 3.0, "hitTime": 1.88, "lastHitTime": 1.88}
    Core._reset_spatial_escape_plan()
    Decision = Core._try_protected_target_wait_decision(Sense, Skills)
    assert Decision.skill.skillId == "dodge_back"
    assert Decision.reason == "protected_target_spatial_escape_dodge"
    assert CombatDistance(Core, Sense, "back") > CombatDistance(Core, Sense, "left")
    Core._remember_spatial_escape_step(Decision, {"level": 1})

    # Codex 2026-08-10: 一段闪避未解锁时等待；解锁且实距仍不足时只衔接一次现有二段后闪。
    Controller.StateType = "dodge"
    Controller.StateId = "fight_dodge_back"
    Controller.FinishState = False
    Decision = Core._try_protected_target_wait_decision(Sense, Skills)
    assert Decision.skill is None
    assert Decision.reason == "protected_target_spatial_escape_wait"
    Controller.FinishState = True
    Decision = Core._try_protected_target_wait_decision(Sense, Skills)
    assert Decision.skill.skillId == "dodge_back"
    assert Decision.reason == "protected_target_spatial_escape_chain"
    # Codex 2026-08-10: 执行层必须把受限撤离链翻译成现有 SWS level=2 输入，而不是再次播放一段闪避。
    Core.attack_internal_cd_ready = lambda Skill: True
    Core.dodge_internal_cd_ready = lambda Skill: True
    Core.record_attack_internal_cd = lambda Skill, reason="": False
    Core.record_dodge_internal_cd = lambda Skill, reason="": False
    Core._prepare_reactive_dodge_input = lambda: True
    Core._remember_far_opener_step = lambda Skill, Reason: False
    Core._remember_air_charge_step = lambda Skill, Reason: False
    Core._remember_step_blade_step = lambda Skill, Reason: False
    Core._remember_dodge_direction = lambda Skill: False
    Core._remember_reaction_kind = lambda Skill, Payload: False
    assert Core.execute_decision(Decision)
    assert Core.mob.inputCalls[-1][1]["level"] == 2
    assert Core.mob.inputCalls[-1][1]["input_event"] == "ai_spatial_escape_chain"
    Decision = Core._try_protected_target_wait_decision(Sense, Skills)
    assert Decision.skill is None
    assert Core.spatialEscapeChainUsed

    # Codex 2026-08-10: 已经离开安全半径就停止闪避；若目标后来重新压入射程，重新开始一轮受限撤离。
    Sense.rangeSense.targetHorizontalDistance = 4.0
    Decision = Core._try_protected_target_wait_decision(Sense, Skills)
    assert Decision.skill is None
    assert Decision.reason == "protected_target_spatial_escape_clear"
    Controller.StateType = "none"
    Controller.StateId = "fight_none"
    Sense.rangeSense.targetHorizontalDistance = 2.0
    Decision = Core._try_protected_target_wait_decision(Sense, Skills)
    assert Decision.skill.skillId == "dodge_back"

    # Codex 2026-08-10: 背对目标时“后闪”会靠近目标，落点预测应改选侧闪而不是固定方向。
    Core.spatialEscapeSafeRadius = 3.55
    Sense.rangeSense.targetAngle = 180.0
    PickedSkill = Core._pick_spatial_escape_skill(Sense, Skills, False)
    assert PickedSkill.skillId in ("dodge_left", "dodge_right")

    # 决策树必须在概率技能、原生近战接管和普通评分之前执行该高优先级分支。
    DecideNode = ReadMethod(CORE_PATH, "MobAICore", "decide")
    CallLines = {}
    for Node in ast.walk(DecideNode):
        if isinstance(Node, ast.Call) and isinstance(Node.func, ast.Attribute):
            CallLines.setdefault(Node.func.attr, []).append(Node.lineno)
    ProtectedLine = min(CallLines["_try_protected_target_wait_decision"])
    assert ProtectedLine < min(CallLines["_try_native_melee_takeover_decision"])
    assert ProtectedLine < min(CallLines["_try_katana_skill_probability_decision"])

    print("max intellect protected target wait valid: wait, non-advance dodge, resume")


def CombatDistance(Core, Sense, Direction):
    return Core._pick_spatial_escape_skill.__globals__["CombatTactics"].predict_dodge_end_distance(Sense, Direction)


if __name__ == "__main__":
    Main()
