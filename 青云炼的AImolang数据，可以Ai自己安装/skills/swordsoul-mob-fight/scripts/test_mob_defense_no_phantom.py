# coding=utf-8
"""Mob 主动防御不得伪造成功格挡的专项回归。"""

import ast
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[4]
MOB_ROOT = PROJECT_ROOT / "src" / "SwordSoul_NewERA_B" / "SwordSoulMobFightScripts"
SWS_ROOT = PROJECT_ROOT / "src" / "SwordSoul_NewERA_B" / "SwordSoulFightScripts"
CORE_PATH = MOB_ROOT / "AI" / "Core.py"
SKILL_PATH = MOB_ROOT / "AI" / "Skill.py"
TRANSLATOR_PATH = MOB_ROOT / "Combat" / "CommandTranslator.py"
CONTROLLER_PATH = MOB_ROOT / "Combat" / "FightController.py"
MOB_SERVER_PATH = MOB_ROOT / "SwordSoulMobServer.py"
BASE_MOB_PATH = MOB_ROOT / "Entities" / "BaseMob.py"
RAVAGER_PATH = MOB_ROOT / "Entities" / "RavagerMob.py"
SWS_SERVER_PATH = SWS_ROOT / "FightSystem" / "FightServer.py"


def ReadClassNode(PathValue, ClassName):
    Tree = ast.parse(PathValue.read_text(encoding="utf-8-sig"))
    return [
        Node for Node in Tree.body
        if isinstance(Node, ast.ClassDef) and Node.name == ClassName
    ][-1]


def ReadMethod(PathValue, ClassName, MethodName):
    ClassNode = ReadClassNode(PathValue, ClassName)
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


def CalledAttributes(MethodNode):
    return {
        Node.func.attr for Node in ast.walk(MethodNode)
        if isinstance(Node, ast.Call) and isinstance(Node.func, ast.Attribute)
    }


def StringConstants(MethodNode):
    return {
        Node.value for Node in ast.walk(MethodNode)
        if isinstance(Node, ast.Constant) and isinstance(Node.value, str)
    }


class ValueObject(object):
    def __init__(self, **Values):
        self.__dict__.update(Values)


class FakeTime(object):
    @staticmethod
    def time():
        return 100.0


class FakeTags(object):
    DEFENSE = "defense"
    DODGE = "dodge"
    DODGE_TO_DEFENSE = "dodge_to_defense"
    ADVANCE = "advance"


class FakeTargetState(object):
    NORMAL_ATTACK = "normal_attack"
    CHARGE_ATTACK = "charge_attack"


class FakeFightState(object):
    def __init__(self, attackLevel=0.0):
        self.DefenseTime = 100.0
        self.attackLevel = attackLevel
        self.cancelDefenseCd = False
        self.no_damage = True


class FakeTactics(object):
    GuardNow = False
    DodgeNow = False
    RESULT_ONLY_DEFENSE_STATE_IDS = (
        "fight_attack_defense",
        "fight_common_defense",
        "fight_perfect_defense",
    )

    @classmethod
    def target_can_guard_now(cls, Sense, TargetInfo):
        return cls.GuardNow

    @classmethod
    def target_can_dodge_now(cls, Sense, TargetInfo):
        return cls.DodgeNow

    @classmethod
    def is_result_only_defense_skill(cls, Skill):
        return getattr(Skill, "stateId", "") in cls.RESULT_ONLY_DEFENSE_STATE_IDS


def BuildTranslator(Requests):
    Harness = BuildHarness(
        "TranslatorHarness",
        TRANSLATOR_PATH,
        "MobCommandTranslator",
        ("ExpressControlDefense",),
        {"time": FakeTime, "mob_trace": lambda *Args: None},
    )()
    Harness.Control_Defense = False
    Harness.AttackState = "none"
    Harness.ReadyAttack = False
    Harness.DefenseState = False
    Harness.DefenseType = "none"
    Harness.DefenseTime = 0.0
    Harness.DefenseCooldownUntil = 0.0
    Harness.TraceId = "test"
    Harness.mob = ValueObject(entityId="mob", fight_controller=None)
    Harness._clear_timer = lambda Name: None
    Harness._create_named_timer = lambda Name, Delay, Func: None
    Harness.BackState = lambda Item, Value: Requests.append((Item, Value)) or True
    return Harness


def Main():
    # Codex 2026-08-07: 默认主动技能池不得再注册成功格挡候选。
    SkillTree = ast.parse(SKILL_PATH.read_text(encoding="utf-8-sig"))
    SkillStrings = {
        Node.value for Node in ast.walk(SkillTree)
        if isinstance(Node, ast.Constant) and isinstance(Node.value, str)
    }
    assert "defense_common" not in SkillStrings
    assert "defense_try" in SkillStrings

    # Codex 2026-08-07: 三层 AI 闸门必须同时保留，防止特殊高分分支绕过效果过滤。
    AbilityFilter = ReadMethod(CORE_PATH, "AbilityFilter", "filter")
    EmergencyCheck = ReadMethod(CORE_PATH, "MobAICore", "_can_use_emergency_skill")
    NormalReaction = ReadMethod(CORE_PATH, "MobAICore", "_try_normal_attack_reaction_pool_decision")
    EmergencyReaction = ReadMethod(CORE_PATH, "MobAICore", "_try_emergency_survival_decision")
    ExecuteDecision = ReadMethod(CORE_PATH, "MobAICore", "execute_decision")
    EmergencyPick = ReadMethod(CORE_PATH, "MobAICore", "_pick_emergency_skill")
    assert "is_result_only_defense_skill" in CalledAttributes(AbilityFilter)
    assert "is_result_only_defense_skill" in CalledAttributes(EmergencyCheck)
    assert "_filter_current_reaction_skills" in CalledAttributes(NormalReaction)
    assert "_filter_current_reaction_skills" in CalledAttributes(EmergencyReaction)
    assert "is_result_only_defense_skill" in CalledAttributes(ExecuteDecision)
    assert "_can_execute_reactive_defense_skill" in CalledAttributes(ExecuteDecision)
    ContinueDefense = ReadMethod(CORE_PATH, "MobAICore", "can_continue_ai_defense")
    assert "target_can_guard_now" in CalledAttributes(ContinueDefense)
    GuardNow = ReadMethod(CORE_PATH, "CombatTactics", "target_can_guard_now")
    StrictFacingCalls = [
        Node for Node in ast.walk(GuardNow)
        if isinstance(Node, ast.Call)
        and isinstance(Node.func, ast.Attribute)
        and Node.func.attr == "target_attack_faces_self"
    ]
    assert len(StrictFacingCalls) == 1
    assert isinstance(StrictFacingCalls[0].args[-1], ast.Constant)
    assert StrictFacingCalls[0].args[-1].value is True
    assert "defense_common" not in StringConstants(EmergencyPick)
    assert "defense_try" in StringConstants(EmergencyPick)

    # Codex 2026-08-07: 通用直接执行和排队接口也必须封死结果态旁路。
    ExecuteFightState = ReadMethod(BASE_MOB_PATH, "SwordSoulMobEntity", "execute_fight_state")
    RequestFightState = ReadMethod(BASE_MOB_PATH, "SwordSoulMobEntity", "request_fight_state")
    for MethodNode in (ExecuteFightState, RequestFightState):
        AttributeLoads = {
            Node.attr for Node in ast.walk(MethodNode)
            if isinstance(Node, ast.Attribute) and isinstance(Node.ctx, ast.Load)
        }
        assert "ReactionResultStateIds" in AttributeLoads
    DirectCalls = []
    BaseHarness = BuildHarness(
        "BaseHarness",
        BASE_MOB_PATH,
        "SwordSoulMobEntity",
        ("execute_fight_state", "request_fight_state"),
        {"mob_log": lambda *Args: None},
    )()
    BaseHarness.hard_enabled = True
    BaseHarness.entityId = "mob"
    BaseHarness.ReactionResultStateIds = FakeTactics.RESULT_ONLY_DEFENSE_STATE_IDS
    BaseHarness.enter_fight_mode = lambda: DirectCalls.append("enter")
    BaseHarness.fight_controller = ValueObject(
        set_state=lambda StateId, Request, Force: DirectCalls.append(StateId) or True
    )
    for ResultStateId in BaseHarness.ReactionResultStateIds:
        assert not BaseHarness.execute_fight_state(ResultStateId)
        assert not BaseHarness.request_fight_state(ResultStateId)
    assert DirectCalls == []
    assert BaseHarness.execute_fight_state("fight_try_defense")
    assert DirectCalls == ["enter", "fight_try_defense"]

    # Codex 2026-08-07: 输入层无条件把主动 common/perfect/attack 归一化为 try。
    for RequestedType in ("common", "perfect", "attack", "try"):
        Requests = []
        Translator = BuildTranslator(Requests)
        assert Translator.ExpressControlDefense(True, {
            "type": RequestedType,
            "input_event": "test_defense",
        })
        assert Translator.DefenseType == "try", RequestedType
        assert not Translator.AIDefenseHeld
        assert Requests == [("DefenseState", True)], (RequestedType, Requests)

    AIRequests = []
    AITranslator = BuildTranslator(AIRequests)
    assert AITranslator.ExpressControlDefense(True, {
        "type": "try",
        "source": "mob_ai_core",
        "input_event": "ai_defense",
    })
    assert AITranslator.AIDefenseHeld

    # Codex 2026-08-07: 闪避接防御同样只能发出 try 输入。
    ChainPayloads = []
    ChainHarness = BuildHarness(
        "ChainHarness",
        TRANSLATOR_PATH,
        "MobCommandTranslator",
        ("_auto_chain_defense_after_dodge",),
    )()
    ChainHarness.DodgeChainDefenseDuration = 0.22
    ChainHarness.ExpressControlDefense = lambda Value, Payload: ChainPayloads.append(Payload) or True
    ChainHarness._create_named_timer = lambda Name, Delay, Func: None
    ChainHarness._auto_release_defense = lambda: None
    assert ChainHarness._auto_chain_defense_after_dodge()
    assert ChainPayloads == [{
        "type": "try",
        "source": "mob_ai_core",
        "input_event": "dodge_chain_defense",
    }]

    # Codex 2026-08-07: AI 举防后威胁消失时，Tick 必须主动发送松开输入。
    ReleasePayloads = []
    HoldHarness = BuildHarness(
        "HoldHarness",
        TRANSLATOR_PATH,
        "MobCommandTranslator",
        ("_enforce_ai_tap_defense",),
        {"time": FakeTime},
    )()
    HoldHarness.Control_Defense = True
    HoldHarness.AIDefenseHeld = True
    HoldHarness.DefenseTime = 100.0
    HoldHarness.mob = ValueObject(
        ai_core=ValueObject(can_continue_ai_defense=lambda: False),
        fight_controller=None,
    )
    HoldHarness.ExpressControlDefense = lambda Value, Payload: ReleasePayloads.append((Value, Payload)) or True
    assert HoldHarness._enforce_ai_tap_defense()
    assert ReleasePayloads == [(False, {"input_event": "defense_threat_lost"})]

    # Codex 2026-08-07: 高优先级反应池按当前时窗过滤，结果态在任何情况下都不可通过。
    FilterHarness = BuildHarness(
        "FilterHarness",
        CORE_PATH,
        "MobAICore",
        ("_filter_current_reaction_skills",),
        {"CombatTactics": FakeTactics, "AISkillTag": FakeTags},
    )()
    Attack = ValueObject(skillId="common_attack", stateId="fight_attack_first", tags=set())
    TryDefense = ValueObject(skillId="defense_try", stateId="fight_try_defense", tags={FakeTags.DEFENSE})
    ResultDefense = ValueObject(skillId="defense_common", stateId="fight_common_defense", tags={FakeTags.DEFENSE})
    DodgeDefense = ValueObject(
        skillId="dodge_to_defense",
        stateId="fight_dodge_back",
        tags={FakeTags.DEFENSE, FakeTags.DODGE, FakeTags.DODGE_TO_DEFENSE},
    )
    Skills = [Attack, TryDefense, ResultDefense, DodgeDefense]
    FakeTactics.GuardNow = False
    FakeTactics.DodgeNow = False
    assert FilterHarness._filter_current_reaction_skills(None, Skills, {}) == [Attack]
    FakeTactics.GuardNow = True
    assert FilterHarness._filter_current_reaction_skills(None, Skills, {}) == [Attack, TryDefense]
    FakeTactics.GuardNow = False
    FakeTactics.DodgeNow = True
    assert FilterHarness._filter_current_reaction_skills(None, Skills, {}) == [Attack, DodgeDefense]

    # Codex 2026-08-10: 拼刀反作用态只能驱动后仰表现，不得把攻击者登记成正在举防。
    RunFightState = ReadMethod(CONTROLLER_PATH, "MobFightController", "RunFightState")
    ParentMap = {
        Child: Parent
        for Parent in ast.walk(RunFightState)
        for Child in ast.iter_child_nodes(Parent)
    }
    DefenseStateCalls = [
        Node for Node in ast.walk(RunFightState)
        if isinstance(Node, ast.Call)
        and isinstance(Node.func, ast.Attribute)
        and Node.func.attr == "set_defense_state"
        and len(Node.args) >= 2
        and isinstance(Node.args[1], ast.Constant)
        and Node.args[1].value is True
    ]
    assert len(DefenseStateCalls) == 1
    Ancestors = []
    Current = DefenseStateCalls[0]
    while Current in ParentMap:
        Current = ParentMap[Current]
        Ancestors.append(Current)
    GuardIfs = [Node for Node in Ancestors if isinstance(Node, ast.If)]
    assert any(
        "fight_attack_defense" in StringConstants(Node)
        and any(isinstance(Part, ast.NotEq) for Part in ast.walk(Node.test))
        for Node in GuardIfs
    )

    # Codex 2026-08-10: 普通/完美格挡都必须拒绝异名回退状态。
    for MethodName in ("OnCommonDefense", "OnPerfectDefense"):
        MethodNode = ReadMethod(CONTROLLER_PATH, "MobFightController", MethodName)
        assert any(
            isinstance(Node, ast.Compare)
            and any(isinstance(Operator, ast.NotEq) for Operator in Node.ops)
            for Node in ast.walk(MethodNode)
        ), MethodName

    # Codex 2026-08-10: 劫掠兽无格挡资源，智力许可和反应回退均必须关闭。
    RavagerClass = ReadClassNode(RAVAGER_PATH, "RavagerMob")
    RavagerAssignments = {
        Target.id: ast.literal_eval(Node.value)
        for Node in RavagerClass.body
        if isinstance(Node, ast.Assign) and len(Node.targets) == 1
        for Target in Node.targets
        if isinstance(Target, ast.Name)
        and Target.id in ("aiIntellectParams", "FightReactionFallbackMap")
    }
    assert RavagerAssignments["aiIntellectParams"]["allowPerfectDefense"] is False
    assert "fight_common_defense" not in RavagerAssignments["FightReactionFallbackMap"]
    assert "fight_perfect_defense" not in RavagerAssignments["FightReactionFallbackMap"]

    MobFightEvent = ReadMethod(MOB_SERVER_PATH, "MobCombatSystem", "OnSWSFightEvent")
    assert "fight_perfect_defense" in StringConstants(MobFightEvent)
    assert "HasFightState" in CalledAttributes(MobFightEvent)

    # Codex 2026-08-10: SWS 真实命中后的格挡回推必须保留，并以 Mob 事务结果决定是否吞伤害。
    SWSServerSource = SWS_SERVER_PATH.read_text(encoding="utf-8-sig")
    assert 'ForwardMobFightEvent("common_defense"' in SWSServerSource
    assert 'ForwardMobFightEvent("perfect_defense"' in SWSServerSource
    PerfectCalls = []
    ExpressDefenseHarness = BuildHarness(
        "ExpressDefenseHarness",
        SWS_SERVER_PATH,
        "FightControlSystem",
        ("ExpressDefense",),
        {
            "time": FakeTime,
            "CallClient": lambda *Args: PerfectCalls.append(Args),
        },
    )()
    HurtState = FakeFightState()
    AttackState = FakeFightState(1.0)
    ExpressDefenseHarness.getEntityFightState = lambda EntityId: HurtState if EntityId == "hurt" else AttackState
    ExpressDefenseHarness.CheckDir = lambda AttackId, OnHurtId: True
    ExpressDefenseHarness.MobAllowsPerfectReaction = lambda EntityId, Reaction: True
    ExpressDefenseHarness.IsMobFightEntity = lambda EntityId: True
    ExpressDefenseHarness.ConsumeCombatWeaponDurability = lambda EntityId: None
    ExpressDefenseHarness.ForwardMobFightEvent = lambda Event, Payload: False
    assert ExpressDefenseHarness.ExpressDefense("attack", "hurt", {"cause": "entity_attack"}) == 1.0
    assert PerfectCalls == []
    assert not HurtState.cancelDefenseCd

    ExpressDefenseHarness.ForwardMobFightEvent = lambda Event, Payload: True
    assert ExpressDefenseHarness.ExpressDefense("attack", "hurt", {"cause": "entity_attack"}) == 0.0
    assert PerfectCalls == [("OnPerfectDefense", "hurt", "attack")]
    assert HurtState.cancelDefenseCd

    # 玩家仍沿用原 SWS 完美格挡结算，不受 Mob 状态能力校验影响。
    PerfectCalls[:] = []
    HurtState.cancelDefenseCd = False
    ExpressDefenseHarness.IsMobFightEntity = lambda EntityId: False
    ExpressDefenseHarness.ForwardMobFightEvent = lambda Event, Payload: False
    assert ExpressDefenseHarness.ExpressDefense("attack", "hurt", {"cause": "entity_attack"}) == 0.0
    assert PerfectCalls == [("OnPerfectDefense", "hurt", "attack")]
    assert HurtState.cancelDefenseCd

    print("mob defense no-phantom guard valid")


if __name__ == "__main__":
    Main()
