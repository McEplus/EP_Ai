# coding=utf-8
"""所有 Mob 未注册状态请求的统一拒绝与输入清理回归。"""

import ast
import copy
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[4]
MOB_SCRIPT_ROOT = PROJECT_ROOT / "src" / "SwordSoul_NewERA_B" / "SwordSoulMobFightScripts"
CONDITIONS_PATH = MOB_SCRIPT_ROOT / "Combat" / "Conditions.py"
CONTROLLER_PATH = MOB_SCRIPT_ROOT / "Combat" / "FightController.py"
TRANSLATOR_PATH = MOB_SCRIPT_ROOT / "Combat" / "CommandTranslator.py"


def ReadTree(PathValue):
    return ast.parse(PathValue.read_text(encoding="utf-8-sig"))


def FindClass(PathValue, ClassName):
    return next(
        Node for Node in ReadTree(PathValue).body
        if isinstance(Node, ast.ClassDef) and Node.name == ClassName
    )


def FindMethod(ClassNode, MethodName):
    return next(
        Node for Node in ClassNode.body
        if isinstance(Node, ast.FunctionDef) and Node.name == MethodName
    )


def BuildClassHarness(Name, PathValue, SourceClassName, MethodNames):
    SourceClass = FindClass(PathValue, SourceClassName)
    Body = [copy.deepcopy(FindMethod(SourceClass, MethodName)) for MethodName in MethodNames]
    HarnessClass = ast.ClassDef(
        name=Name,
        bases=[ast.Name(id="object", ctx=ast.Load())],
        keywords=[],
        body=Body,
        decorator_list=[],
    )
    Module = ast.fix_missing_locations(ast.Module(body=[HarnessClass], type_ignores=[]))
    Namespace = {"mob_trace": lambda *Args: None}
    exec(compile(Module, str(PathValue), "exec"), Namespace)
    return Namespace[Name]


class ValueObject(object):
    def __init__(self, **Values):
        self.__dict__.update(Values)


def BuildControl():
    Harness = BuildClassHarness(
        "TranslatorHarness",
        TRANSLATOR_PATH,
        "MobCommandTranslator",
        ("RejectUnavailableStateRequest", "clear_attack_input", "clear_dodge_input"),
    )
    Control = Harness()
    Control.mob = ValueObject(entityId="mob-test")
    Control.TraceId = "reject-test"
    Control.AttackState = "active"
    Control.Control_Attack = True
    Control.ReadyAttack = True
    Control.AIChargeHeld = True
    Control.FastControlRisingDragon = True
    Control.ForcedSneakingAttackLevel = 4
    Control.Control_Skill = True
    Control.ReadySkill = True
    Control.SkillState = "skill"
    Control.Control_Defense = True
    Control.DefenseState = True
    Control.DefenseType = "try"
    Control.DefenseCooldownUntil = 99.0
    Control.Control_Dodge = True
    Control.DodgeState = True
    Control.DodgeType = "common"
    Control.DodgeLevel = 2
    Control.DodgeChainDefenseDuration = 9.0
    Control.SecondJumpState = True
    Control.JumpState = True
    Control.Control_HockRope = True
    Control.HockRopeState = "shoot"
    Control.HockRopeFlying = True
    Control.HitType = "heavy"
    Control.StiffTime = 3.0
    Control.StepState = True
    Control.ClearedTimers = []
    Control.CommonCleared = False
    Control.StepGuardCleared = False
    Control.FallbackCleared = False
    Control._clear_timer = lambda Name: Control.ClearedTimers.append(Name)
    Control.clearCommonAttackState = lambda: setattr(Control, "CommonCleared", True)
    Control._set_step_guard_state = lambda State: setattr(Control, "StepGuardCleared", not State)
    Control.ClearFightNoneResidue = lambda: setattr(Control, "FallbackCleared", True)
    return Control


def AssertTranslatorCleanup():
    Control = BuildControl()
    assert Control.RejectUnavailableStateRequest("fight_attack_up", "common_attack")
    assert Control.AttackState == "none" and not Control.Control_Attack and Control.CommonCleared

    Control = BuildControl()
    Control.RejectUnavailableStateRequest("fight_attack_sneaking_4", "sneaking_attack")
    assert Control.AttackState == "none" and Control.ForcedSneakingAttackLevel == 0

    Control = BuildControl()
    Control.RejectUnavailableStateRequest("fight_skill_missing", "skill")
    assert Control.SkillState == "none" and not Control.Control_Skill and "SkillStateTimer" in Control.ClearedTimers

    Control = BuildControl()
    Control.RejectUnavailableStateRequest("fight_try_defense", "defense")
    assert not Control.Control_Defense and not Control.DefenseState and Control.DefenseType == "none"

    Control = BuildControl()
    Control.RejectUnavailableStateRequest("fight_dodge_forward", "dodge")
    assert not Control.Control_Dodge and not Control.DodgeState and Control.DodgeType == "none"

    Control = BuildControl()
    Control.RejectUnavailableStateRequest("fight_second_jump_forward", "second_jump")
    assert not Control.SecondJumpState and "SecondJumpStateTimer" in Control.ClearedTimers

    Control = BuildControl()
    Control.RejectUnavailableStateRequest("fight_jump", "jump")
    assert not Control.JumpState and Control.StepGuardCleared

    Control = BuildControl()
    Control.RejectUnavailableStateRequest("fight_shoot_hock_rope", "hock_rope")
    assert not Control.Control_HockRope and Control.HockRopeState == "none" and not Control.HockRopeFlying

    Control = BuildControl()
    Control.RejectUnavailableStateRequest("fight_hit_heavy", "hit")
    assert Control.HitType == "none" and Control.StiffTime == 0.0

    Control = BuildControl()
    Control.RejectUnavailableStateRequest("fight_step", "step")
    assert not Control.StepState and "StepStateTimer" in Control.ClearedTimers

    Control = BuildControl()
    Control.RejectUnavailableStateRequest("fight_unknown", "none")
    assert Control.FallbackCleared


class PendingCondition(object):
    def __init__(self, Pending=True):
        self.Pending = Pending

    def IsRequestPending(self):
        return self.Pending

    def Compute(self):
        raise AssertionError("unavailable state must reject before Compute")


class FakeControl(object):
    def __init__(self):
        self.SkillState = "none"
        self.Rejections = []

    def RejectUnavailableStateRequest(self, StateId, StateType):
        self.Rejections.append((StateId, StateType))
        return True


class FakeMob(object):
    def __init__(self):
        self.entityId = "mob-test"
        self.command_translator = FakeControl()

    def HasFightState(self, StateId):
        return False


def AssertControllerBoundary():
    Harness = BuildClassHarness(
        "ControllerHarness",
        CONTROLLER_PATH,
        "MobFightController",
        ("TranslatingState",),
    )
    Controller = Harness()
    Controller.mob = FakeMob()
    Controller.FinishState = True
    Controller.NextSkillStateId = ""
    Controller.NowStateId = "fight_none"
    Controller.StateTypeMap = {"fight_attack_up": "common_attack"}
    Controller.ConditionOrder = [("fight_attack_up", PendingCondition())]
    Controller.get_trace_id = lambda: "reject-test"
    Controller.set_state = lambda *Args: (_ for _ in ()).throw(AssertionError("missing state entered"))
    assert not Controller.TranslatingState("input")
    assert Controller.mob.command_translator.Rejections == [("fight_attack_up", "common_attack")]

    Controller.mob.command_translator.SkillState = "skill"
    Controller.NextSkillStateId = "fight_skill_missing"
    Controller.ConditionOrder = []
    assert not Controller.TranslatingState("input")
    assert Controller.mob.command_translator.Rejections[-1] == ("fight_skill_missing", "skill")
    assert Controller.NextSkillStateId == ""


def AssertConditionCoverage():
    Tree = ReadTree(CONDITIONS_PATH)
    RequiredClasses = {
        "ToAttackStage", "ToSneaking", "ToSneakingAttack", "ToDefense", "ToDodge",
        "ToPerfectDodge", "ToSecondJump", "ToJump", "ToSkill", "ToHockRope", "ToStep", "ToHit",
    }
    CoveredClasses = {
        Node.name for Node in Tree.body
        if isinstance(Node, ast.ClassDef)
        and any(isinstance(Child, ast.FunctionDef) and Child.name == "IsRequestPending" for Child in Node.body)
    }
    assert RequiredClasses <= CoveredClasses, sorted(RequiredClasses - CoveredClasses)

    ControllerClass = FindClass(CONTROLLER_PATH, "MobFightController")
    StateTypeAssignment = next(
        Node for Node in ControllerClass.body
        if isinstance(Node, ast.Assign)
        and any(isinstance(Target, ast.Name) and Target.id == "StateTypeMap" for Target in Node.targets)
    )
    StateTypes = set(ast.literal_eval(StateTypeAssignment.value).values()) - {"none"}
    HandledTypes = {
        "common_attack", "execute", "sneaking", "sneaking_attack", "skill", "super_skill",
        "defense", "dodge", "second_jump", "jump", "hock_rope", "hit", "step",
    }
    assert StateTypes <= HandledTypes, sorted(StateTypes - HandledTypes)


def Main():
    # Codex 2026-08-04: 全实体统一验证“先识别请求、再拒绝未注册状态、最后清理对应输入”。
    AssertConditionCoverage()
    AssertTranslatorCleanup()
    AssertControllerBoundary()
    print("unavailable state request rejection valid: all mob state types covered")


if __name__ == "__main__":
    Main()
