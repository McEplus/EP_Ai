# coding=utf-8
"""Mob 强制反应事务、实体降级与 fight_none 残留清理回归。"""

import ast
import copy
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[4]
SCRIPT_ROOT = PROJECT_ROOT / "src" / "SwordSoul_NewERA_B" / "SwordSoulMobFightScripts"
BASE_MOB_PATH = SCRIPT_ROOT / "Entities" / "BaseMob.py"
IRON_GOLEM_PATH = SCRIPT_ROOT / "Entities" / "IronGolemMob.py"
CONTROLLER_PATH = SCRIPT_ROOT / "Combat" / "FightController.py"
TRANSLATOR_PATH = SCRIPT_ROOT / "Combat" / "CommandTranslator.py"


def ReadTree(PathValue):
    return ast.parse(PathValue.read_text(encoding="utf-8-sig"))


def FindClassWithMethod(Tree, MethodName):
    return next(
        Node for Node in Tree.body
        if isinstance(Node, ast.ClassDef)
        and any(
            isinstance(Child, ast.FunctionDef) and Child.name == MethodName
            for Child in Node.body
        )
    )


def FindMethod(ClassNode, MethodName):
    return next(
        Node for Node in ClassNode.body
        if isinstance(Node, ast.FunctionDef) and Node.name == MethodName
    )


def CompileMethod(MethodNode, PathValue, ExtraNamespace=None):
    Module = ast.fix_missing_locations(ast.Module(body=[copy.deepcopy(MethodNode)], type_ignores=[]))
    Namespace = {"mob_trace": lambda *Args: None}
    Namespace.update(ExtraNamespace or {})
    exec(compile(Module, str(PathValue), "exec"), Namespace)
    return Namespace[MethodNode.name]


def ReadClassAssignment(PathValue, ClassName, FieldName):
    Tree = ReadTree(PathValue)
    ClassNode = next(
        Node for Node in Tree.body
        if isinstance(Node, ast.ClassDef) and Node.name == ClassName
    )
    AssignNode = next(
        Node for Node in ClassNode.body
        if isinstance(Node, ast.Assign)
        and any(isinstance(Target, ast.Name) and Target.id == FieldName for Target in Node.targets)
    )
    return ast.literal_eval(AssignNode.value)


def AssertIronGolemFallbackResolution():
    ExpectedFallbackMap = {
        "fight_hit_vertigo": "fight_hit_light",
        "fight_hit_control": "fight_hit_light",
        "fight_dodge_forward_perfect": "fight_dodge_forward",
        "fight_dodge_back_perfect": "fight_dodge_back",
        "fight_dodge_left_perfect": "fight_dodge_left",
        "fight_dodge_right_perfect": "fight_dodge_right",
        "fight_dodge_forward_second": "fight_dodge_forward",
        "fight_dodge_back_second": "fight_dodge_back",
        "fight_dodge_left_second": "fight_dodge_left",
        "fight_dodge_right_second": "fight_dodge_right",
    }
    assert ReadClassAssignment(IRON_GOLEM_PATH, "IronGolemMob", "FightReactionFallbackMap") == ExpectedFallbackMap
    IronTree = ReadTree(IRON_GOLEM_PATH)
    AllowedNode = next(
        Node for Node in IronTree.body
        if isinstance(Node, ast.Assign)
        and any(
            isinstance(Target, ast.Name) and Target.id == "IRON_GOLEM_ALLOWED_STATE_IDS"
            for Target in Node.targets
        )
    )
    AllowedStates = ast.literal_eval(AllowedNode.value)
    # Codex 2026-08-03: 每个降级目标都必须属于铁傀儡已制作动作白名单。
    assert set(ExpectedFallbackMap.values()) <= AllowedStates
    assert not (set(ExpectedFallbackMap) & AllowedStates)

    BaseClass = FindClassWithMethod(ReadTree(BASE_MOB_PATH), "ResolveFightReactionState")
    Resolve = CompileMethod(FindMethod(BaseClass, "ResolveFightReactionState"), BASE_MOB_PATH)

    class ResolveHarness(object):
        FightReactionFallbackMap = ExpectedFallbackMap

        def __init__(self, Available):
            self.Available = set(Available)

        def HasFightState(self, StateId):
            return StateId in self.Available

    Harness = ResolveHarness(("fight_hit_vertigo", "fight_hit_light"))
    assert Resolve(Harness, "fight_hit_vertigo") == "fight_hit_vertigo"
    Harness = ResolveHarness(("fight_hit_light",))
    assert Resolve(Harness, "fight_hit_vertigo") == "fight_hit_light"
    Harness = ResolveHarness(())
    assert Resolve(Harness, "fight_hit_vertigo") == ""
    assert Resolve(Harness, "fight_step") == ""
    return len(ExpectedFallbackMap)


class FakeControl(object):
    def __init__(self):
        self.HitType = "old_hit"
        self.StiffTime = 4.0
        self.DefenseType = "old_defense"


class FakeMob(object):
    def __init__(self):
        self.entityId = "mob-1"
        self.command_translator = FakeControl()


class ReactionHarness(object):
    def __init__(self, SetStateResult=True, RaiseStateError=False):
        self.mob = FakeMob()
        self.NowStateId = "fight_attack_first"
        self.SetStateResult = SetStateResult
        self.RaiseStateError = RaiseStateError
        self.StateCalls = []

    def get_trace_id(self):
        return "test"

    def set_state(self, StateId, Request, Force):
        self.StateCalls.append((StateId, Request, Force))
        if self.RaiseStateError:
            raise RuntimeError("state failure")
        return self.SetStateResult


def AssertReactionTransaction():
    ControllerClass = FindClassWithMethod(ReadTree(CONTROLLER_PATH), "TryReactionState")
    Transaction = CompileMethod(FindMethod(ControllerClass, "TryReactionState"), CONTROLLER_PATH)

    SuccessHarness = ReactionHarness(True)
    Result = Transaction(
        SuccessHarness,
        "fight_hit_heavy",
        "fight_hit_light",
        {"HitType": "light", "StiffTime": 1.0},
        {"reaction_hit_type": "heavy"},
    )
    assert Result is True
    assert SuccessHarness.mob.command_translator.HitType == "light"
    assert SuccessHarness.mob.command_translator.StiffTime == 1.0
    StateId, Request, Force = SuccessHarness.StateCalls[-1]
    assert StateId == "fight_hit_light" and Force is True
    assert Request["reaction_requested_state"] == "fight_hit_heavy"
    assert Request["reaction_fallback_from"] == "fight_hit_heavy"

    FailureHarness = ReactionHarness(False)
    assert Transaction(
        FailureHarness,
        "fight_hit_heavy",
        "fight_hit_light",
        {"HitType": "light", "StiffTime": 1.0},
    ) is False
    assert FailureHarness.mob.command_translator.HitType == "old_hit"
    assert FailureHarness.mob.command_translator.StiffTime == 4.0

    ErrorHarness = ReactionHarness(True, True)
    try:
        Transaction(
            ErrorHarness,
            "fight_hit_heavy",
            "fight_hit_light",
            {"HitType": "light", "StiffTime": 1.0},
        )
        raise AssertionError("state exception must propagate")
    except RuntimeError:
        pass
    assert ErrorHarness.mob.command_translator.HitType == "old_hit"
    assert ErrorHarness.mob.command_translator.StiffTime == 4.0

    # Codex 2026-08-03: 所有强制入口必须走事务，禁止恢复提前 CancelCD 的破坏性顺序。
    for MethodName in (
        "OnAttackDefense", "OnCommonDefense", "OnPerfectDefense", "OnPerfectDodge",
        "OnHitHeavy", "OnHitCommon", "OnStep",
    ):
        MethodNode = FindMethod(ControllerClass, MethodName)
        CallNames = [
            Node.func.attr for Node in ast.walk(MethodNode)
            if isinstance(Node, ast.Call) and isinstance(Node.func, ast.Attribute)
        ]
        assert "ResolveReactionState" in CallNames, MethodName
        assert "TryReactionState" in CallNames, MethodName
        assert "CancelCD" not in CallNames, MethodName
    return 7


class CleanupHarness(object):
    def __init__(self):
        self.TraceId = "test"
        self.mob = FakeMob()
        self.Control_Attack = False
        self.Control_Defense = False
        self.Control_Dodge = False
        self.Control_HockRope = False
        self.AttackState = "common_attack"
        self.DefenseState = True
        self.DefenseType = "attack"
        self.DodgeState = True
        self.DodgeType = "perfect"
        self.DodgeLevel = 2
        self.HockRopeState = "shoot"
        self.JumpState = True
        self.SecondJumpState = True
        self.StepState = True
        self.SkillState = "skill"
        self.HitType = "control"
        self.BudgeSneaking = True
        self.ReadyAttack = True
        self.ReadySkill = True
        self.ClearedTimers = []

    def _clear_timer(self, TimerName):
        self.ClearedTimers.append(TimerName)

    def clear_attack_input(self):
        self.AttackState = "none"
        self.Control_Attack = False
        self.ReadyAttack = False
        self._clear_timer("AttackStateTimer")
        self._clear_timer("LongPressAttack")

    def clear_dodge_input(self, ClearControl=True):
        self.DodgeState = False
        self.DodgeType = "none"
        self.DodgeLevel = 1
        if ClearControl:
            self.Control_Dodge = False
        self._clear_timer("DodgeLevelTimer")
        self._clear_timer("DodgeTypeTimer")


def AssertFightNoneCleanup():
    TranslatorClass = FindClassWithMethod(ReadTree(TRANSLATOR_PATH), "ClearFightNoneResidue")
    Cleanup = CompileMethod(FindMethod(TranslatorClass, "ClearFightNoneResidue"), TRANSLATOR_PATH)

    IdleHarness = CleanupHarness()
    assert Cleanup(IdleHarness) is True
    assert IdleHarness.AttackState == "none" and IdleHarness.ReadyAttack is False
    assert IdleHarness.DefenseState is False and IdleHarness.DefenseType == "none"
    assert IdleHarness.DodgeState is False and IdleHarness.DodgeType == "none" and IdleHarness.DodgeLevel == 1
    assert IdleHarness.HockRopeState == "none"
    assert IdleHarness.JumpState is False and IdleHarness.SecondJumpState is False
    assert IdleHarness.StepState is False and IdleHarness.SkillState == "none" and IdleHarness.HitType == "none"

    HeldHarness = CleanupHarness()
    HeldHarness.Control_Attack = True
    HeldHarness.Control_Defense = True
    HeldHarness.Control_Dodge = True
    HeldHarness.Control_HockRope = True
    HeldHarness.AttackState = "sneaking"
    HeldHarness.DefenseState = True
    HeldHarness.DefenseType = "try"
    HeldHarness.DodgeState = True
    HeldHarness.DodgeType = "common"
    HeldHarness.HockRopeState = "aim"
    assert Cleanup(HeldHarness) is True
    assert HeldHarness.Control_Attack is True and HeldHarness.ReadyAttack is True
    assert HeldHarness.Control_Defense is True and HeldHarness.DefenseState is True and HeldHarness.DefenseType == "try"
    assert HeldHarness.Control_Dodge is True and HeldHarness.DodgeState is True and HeldHarness.DodgeType == "common"
    assert HeldHarness.Control_HockRope is True and HeldHarness.HockRopeState == "aim"
    assert HeldHarness.HitType == "none" and HeldHarness.StepState is False

    ReleasedDodgeHarness = CleanupHarness()
    ReleasedDodgeHarness.Control_Dodge = True
    ReleasedDodgeHarness.DodgeState = False
    assert Cleanup(ReleasedDodgeHarness) is True
    assert ReleasedDodgeHarness.Control_Dodge is True
    assert ReleasedDodgeHarness.DodgeType == "none" and ReleasedDodgeHarness.DodgeLevel == 1

    ControllerText = CONTROLLER_PATH.read_text(encoding="utf-8")
    assert 'self.NextSkillStateId = ""' in ControllerText
    return 3


class InterruptedChargeHarness(object):
    def __init__(self, AIChargeHeld=True):
        self.AIChargeHeld = AIChargeHeld
        self.AttackState = "sneaking"
        self.Control_Attack = True
        self.ReadyAttack = True
        self.TraceId = "ai:charge_hold:test"
        self.mob = FakeMob()
        self.ClearedTimers = []

    def clear_attack_input(self):
        self.AttackState = "none"
        self.Control_Attack = False
        self.ReadyAttack = False
        self.AIChargeHeld = False
        self.ClearedTimers.append("AutoReleaseCharge")


def AssertInterruptedAIChargeCleanup():
    TranslatorClass = FindClassWithMethod(ReadTree(TRANSLATOR_PATH), "_clear_interrupted_ai_charge")
    CleanupNode = FindMethod(TranslatorClass, "_clear_interrupted_ai_charge")
    Cleanup = CompileMethod(CleanupNode, TRANSLATOR_PATH)

    # Codex 2026-08-04: AI 模拟蓄力被强制反应打断时必须当帧撤销，不能依赖距离看门狗事后恢复。
    HitHarness = InterruptedChargeHarness(True)
    assert Cleanup(HitHarness, "fight_sneaking", "hit") is True
    assert HitHarness.AttackState == "none"
    assert HitHarness.Control_Attack is False and HitHarness.ReadyAttack is False
    assert HitHarness.AIChargeHeld is False
    assert "AutoReleaseCharge" in HitHarness.ClearedTimers

    ReleaseHarness = InterruptedChargeHarness(True)
    assert Cleanup(ReleaseHarness, "fight_sneaking", "sneaking_attack") is False
    assert ReleaseHarness.Control_Attack is True and ReleaseHarness.AIChargeHeld is True

    HoldHarness = InterruptedChargeHarness(True)
    assert Cleanup(HoldHarness, "fight_sneaking", "sneaking") is False
    assert HoldHarness.Control_Attack is True and HoldHarness.AIChargeHeld is True

    PlayerHarness = InterruptedChargeHarness(False)
    assert Cleanup(PlayerHarness, "fight_sneaking", "hit") is False
    assert PlayerHarness.Control_Attack is True

    for MethodName in ("on_fight_state_started", "on_fight_state_reset"):
        MethodNode = FindMethod(TranslatorClass, MethodName)
        assert any(
            isinstance(Node, ast.Call)
            and isinstance(Node.func, ast.Attribute)
            and Node.func.attr == "_clear_interrupted_ai_charge"
            for Node in ast.walk(MethodNode)
        ), MethodName
    ClearAttackNode = FindMethod(TranslatorClass, "clear_attack_input")
    ClearAttackText = ast.unparse(ClearAttackNode)
    assert "self.AIChargeHeld = False" in ClearAttackText
    assert "AutoReleaseCharge" in ClearAttackText
    return 4


class FakeMobCombatCommand(object):
    ATTACK = "attack"
    CHARGE = "charge"
    SNEAKING_ATTACK = "sneaking_attack"
    DEFENSE = "defense"
    DODGE = "dodge"
    SNEAKING = "sneaking"
    JUMP = "jump"
    SECOND_JUMP = "second_jump"
    STEP = "step"
    SKILL = "skill"
    SUPER_SKILL = "super_skill"
    HOCK_ROPE_AIM = "hock_rope_aim"
    HOCK_ROPE_SHOOT = "hock_rope_shoot"
    HOCK_ROPE_FLYING = "hock_rope_flying"


class TapInputHarness(object):
    def __init__(self):
        self.mob = type("Mob", (), {
            "entityId": "iron-golem-1",
            "fight_controller": type("Controller", (), {"get_state_id": lambda Self: "fight_attack_first"})(),
        })()
        self.TraceId = "-"
        self.TraceCommand = None
        self.direction = "back"
        self.AttackState = "none"
        self.DefenseState = False
        self.DefenseType = "none"
        self.DodgeState = False
        self.DodgeType = "none"
        self.DodgeLevel = 1
        self.Control_Defense = False
        self.Control_Dodge = False
        self.CreatedTimers = []

    def _sync_native_context(self, Payload):
        return None

    def ExpressControlDefense(self, Value, Payload=None):
        # 模拟输入字段已写入、但当前不可切换帧拒绝进入状态。
        self.Control_Defense = bool(Value)
        self.DefenseState = bool(Value)
        self.DefenseType = "try" if Value else "none"
        return False

    def ExpressControlDodge(self, Value, Payload=None):
        self.Control_Dodge = bool(Value)
        self.DodgeState = bool(Value)
        self.DodgeType = "common" if Value else "none"
        return False

    def _create_named_timer(self, Name, Duration, Func):
        self.CreatedTimers.append((Name, Duration, Func))
        return Name

    def _auto_release_defense(self):
        return None

    def _auto_release_dodge(self):
        return None


def AssertRejectedAITapStillSchedulesRelease():
    TranslatorClass = FindClassWithMethod(ReadTree(TRANSLATOR_PATH), "input_command")
    InputCommand = CompileMethod(
        FindMethod(TranslatorClass, "input_command"),
        TRANSLATOR_PATH,
        {
            "MobCombatCommand": FakeMobCombatCommand,
            "MOB_COMBAT_COMMAND_LIST": (
                FakeMobCombatCommand.ATTACK,
                FakeMobCombatCommand.CHARGE,
                FakeMobCombatCommand.SNEAKING_ATTACK,
                FakeMobCombatCommand.DEFENSE,
                FakeMobCombatCommand.DODGE,
                FakeMobCombatCommand.SNEAKING,
                FakeMobCombatCommand.JUMP,
                FakeMobCombatCommand.SECOND_JUMP,
                FakeMobCombatCommand.STEP,
                FakeMobCombatCommand.SKILL,
                FakeMobCombatCommand.SUPER_SKILL,
                FakeMobCombatCommand.HOCK_ROPE_AIM,
                FakeMobCombatCommand.HOCK_ROPE_SHOOT,
                FakeMobCombatCommand.HOCK_ROPE_FLYING,
            ),
            "mob_log": lambda *Args: None,
        },
    )

    # Codex 2026-08-04: 状态拒绝不能吞掉 AI 点按的松开，且失败闪避不能误触发连锁格挡。
    DefenseHarness = TapInputHarness()
    assert InputCommand(
        DefenseHarness,
        FakeMobCombatCommand.DEFENSE,
        {"pressed": True, "source": "mob_ai_core"},
        0.22,
    ) is False
    assert [(Name, Duration) for Name, Duration, Func in DefenseHarness.CreatedTimers] == [
        ("AutoReleaseDefense", 0.22)
    ]

    DodgeHarness = TapInputHarness()
    assert InputCommand(
        DodgeHarness,
        FakeMobCombatCommand.DODGE,
        {"pressed": True, "source": "mob_ai_core"},
        0.15,
    ) is False
    assert [(Name, Duration) for Name, Duration, Func in DodgeHarness.CreatedTimers] == [
        ("AutoReleaseDodge", 0.15)
    ]
    return 2


def Main():
    FallbackCount = AssertIronGolemFallbackResolution()
    TransactionCount = AssertReactionTransaction()
    CleanupCount = AssertFightNoneCleanup()
    InterruptedChargeCount = AssertInterruptedAIChargeCleanup()
    RejectedTapCount = AssertRejectedAITapStillSchedulesRelease()
    print(
        "mob reaction transaction valid: fallbacks=%d transactional_entries=%d cleanup_cases=%d interrupted_charge=%d rejected_tap_release=%d"
        % (FallbackCount, TransactionCount, CleanupCount, InterruptedChargeCount, RejectedTapCount)
    )


if __name__ == "__main__":
    Main()
