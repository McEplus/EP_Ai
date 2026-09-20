# coding=utf-8
"""Mob 完美格挡与完美闪避智力边界回归检查。"""

import ast
import runpy
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[4]
SCRIPT_ROOT = PROJECT_ROOT / "src" / "SwordSoul_NewERA_B"
MOB_ROOT = SCRIPT_ROOT / "SwordSoulMobFightScripts"
INTELLECT_PATH = MOB_ROOT / "AI" / "Intellect.py"
CONDITIONS_PATH = MOB_ROOT / "Combat" / "Conditions.py"
CONTROLLER_PATH = MOB_ROOT / "Combat" / "FightController.py"
MOB_SERVER_PATH = MOB_ROOT / "SwordSoulMobServer.py"
SWS_SERVER_PATH = SCRIPT_ROOT / "SwordSoulFightScripts" / "FightSystem" / "FightServer.py"


def ReadClass(PathValue, ClassName):
    Tree = ast.parse(PathValue.read_text(encoding="utf-8-sig"))
    return next(Node for Node in Tree.body if isinstance(Node, ast.ClassDef) and Node.name == ClassName)


def ReadMethod(PathValue, ClassName, MethodName):
    ClassNode = ReadClass(PathValue, ClassName)
    return next(
        Node for Node in ClassNode.body
        if isinstance(Node, ast.FunctionDef) and Node.name == MethodName
    )


def BuildClassHarness(Name, PathValue, SourceClassName, MethodNames, Namespace=None, ExtraNodes=None):
    Methods = list(ExtraNodes or []) + [
        ReadMethod(PathValue, SourceClassName, MethodName) for MethodName in MethodNames
    ]
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


def CalledMethods(MethodNode):
    return {
        Node.func.attr for Node in ast.walk(MethodNode)
        if isinstance(Node, ast.Call) and isinstance(Node.func, ast.Attribute)
    }


class ValueObject(object):
    def __init__(self, **Values):
        self.__dict__.update(Values)


class StateType(object):
    DEFENSE = "defense"
    DODGE = "dodge"


class SequenceRandom(object):
    Values = []

    @classmethod
    def random(cls):
        return cls.Values.pop(0)


def Main():
    # Codex 2026-08-04: low/mid 能力边界必须同时约束 SWS 权威判定、事件降级和状态条件。
    IntellectModule = runpy.run_path(str(INTELLECT_PATH))
    ResolveIntellect = IntellectModule["resolve_intellect"]
    Low = ResolveIntellect(ValueObject(aiIntellect="low", aiIntellectParams=None))
    Mid = ResolveIntellect(ValueObject(aiIntellect="mid", aiIntellectParams=None))
    High = ResolveIntellect(ValueObject(aiIntellect="high", aiIntellectParams=None))

    BaseCondition = ReadClass(CONDITIONS_PATH, "MobTranslateCondition")
    ConditionHarnessModule = ast.Module(
        body=[
            BaseCondition,
            ReadClass(CONDITIONS_PATH, "ToDefense"),
            ReadClass(CONDITIONS_PATH, "ToPerfectDodge"),
        ],
        type_ignores=[],
    )
    ast.fix_missing_locations(ConditionHarnessModule)
    ConditionNamespace = {"MobCombatStateType": StateType}
    exec(compile(ConditionHarnessModule, str(CONDITIONS_PATH), "exec"), ConditionNamespace)

    def MakeMob(Intellect):
        Control = ValueObject(
            HitType="none",
            DefenseType="perfect",
            direction="left",
            DodgeType="perfect",
            DefenseNeedPhysical=10.0,
            DodgeNeedPhysical=20.0,
            CheckPhysical=lambda Cost: True,
        )
        return ValueObject(
            ai_core=ValueObject(intellect=Intellect),
            command_translator=Control,
            has_feature=lambda Feature: True,
        )

    assert not ConditionNamespace["ToDefense"](MakeMob(Low), "perfect").Compute()
    assert ConditionNamespace["ToDefense"](MakeMob(Mid), "perfect").Compute()
    assert not ConditionNamespace["ToPerfectDodge"](MakeMob(Low), "left").Compute()
    assert not ConditionNamespace["ToPerfectDodge"](MakeMob(Mid), "left").Compute()
    assert ConditionNamespace["ToPerfectDodge"](MakeMob(High), "left").Compute()

    ControllerHarness = BuildClassHarness(
        "ControllerHarness",
        CONTROLLER_PATH,
        "MobFightController",
        ("OnPerfectDefense", "OnPerfectDodge"),
    )
    Controller = ControllerHarness()
    Controller.is_unbreakable_execute_break_time = lambda: False
    Controller.mob = MakeMob(Low)
    Controller.OnCommonDefense = lambda: "common_defense"
    assert Controller.OnPerfectDefense("attacker") == "common_defense"

    Decisions = []
    Controller.mob = MakeMob(Mid)
    Controller.mob.command_translator.SwordSoulValue = 0.0
    Controller.mob.command_translator.SwordSoulValue_MAX = 100.0
    Controller.ResolveReactionState = lambda StateId: StateId
    Controller.TryReactionState = lambda Requested, Resolved, Changes, Request=None: Decisions.append(
        (Requested, Resolved, dict(Changes))
    ) or True
    assert Controller.OnPerfectDodge()
    assert Decisions[-1][0] == "fight_dodge_left"
    assert Decisions[-1][2]["DodgeType"] == "common"
    assert Controller.mob.command_translator.SwordSoulValue == 0.0

    Controller.mob = MakeMob(High)
    Controller.mob.command_translator.SwordSoulValue = 0.0
    Controller.mob.command_translator.SwordSoulValue_MAX = 100.0
    assert Controller.OnPerfectDodge()
    assert Decisions[-1][0] == "fight_dodge_left_perfect"
    assert Decisions[-1][2]["DodgeType"] == "perfect"
    assert Controller.mob.command_translator.SwordSoulValue == 50.0

    SWSHarness = BuildClassHarness(
        "SWSHarness",
        SWS_SERVER_PATH,
        "FightControlSystem",
        ("MobAllowsPerfectReaction",),
    )()
    SWSHarness.IsMobFightEntity = lambda EntityId: EntityId == "mob"
    SWSHarness.ForwardMobFightEvent = lambda EventType, Payload: EventType == "can_trigger_perfect_defense"
    assert SWSHarness.MobAllowsPerfectReaction("player", "perfect_dodge")
    assert not SWSHarness.MobAllowsPerfectReaction("mob", "perfect_dodge")
    assert SWSHarness.MobAllowsPerfectReaction("mob", "perfect_defense")
    assert "MobAllowsPerfectReaction" in CalledMethods(ReadMethod(SWS_SERVER_PATH, "FightControlSystem", "ExpressDefense"))
    assert "MobAllowsPerfectReaction" in CalledMethods(ReadMethod(SWS_SERVER_PATH, "FightControlSystem", "ExpressDodge"))

    MobServerHarness = BuildClassHarness(
        "MobServerHarness",
        MOB_SERVER_PATH,
        "MobCombatSystem",
        ("try_native_attack_safety_reaction",),
        {"random": SequenceRandom, "mob_trace": lambda *Args: None},
    )()
    EnteredStates = []
    NativeMob = MakeMob(Low)
    NativeMob.fight_controller = ValueObject()
    MobServerHarness.get_or_create_mob = lambda EntityId, Create: NativeMob
    MobServerHarness.get_sws_fight_state = lambda EntityId: None
    MobServerHarness.get_native_attack_dodge_direction = lambda: ("left", 0.0)
    MobServerHarness.enter_native_attack_guard_state = lambda ControllerObj, StateId, SourceId: EnteredStates.append(StateId) or True
    SequenceRandom.Values = [0.0, 0.0, 0.0]
    Args = {"cause": "entity_attack", "srcId": "attacker", "damage": 5.0}
    assert MobServerHarness.try_native_attack_safety_reaction("mob", Args)
    assert EnteredStates[-1] == "fight_dodge_left"

    NativeMob.ai_core.intellect = Mid
    SequenceRandom.Values = [0.0, 0.9, 0.0]
    Args = {"cause": "entity_attack", "srcId": "attacker", "damage": 5.0}
    assert MobServerHarness.try_native_attack_safety_reaction("mob", Args)
    assert EnteredStates[-1] == "fight_perfect_defense"
    print("perfect reaction intellect valid: low=common_only mid=perfect_defense_only high=all")


if __name__ == "__main__":
    Main()
