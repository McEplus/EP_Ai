# coding=utf-8
"""铁傀儡普攻连段与被动蓄力闭环回归检查。"""

import ast
import random
import runpy
import time
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[4]
MOB_SCRIPT_ROOT = PROJECT_ROOT / "src" / "SwordSoul_NewERA_B" / "SwordSoulMobFightScripts"
CORE_PATH = MOB_SCRIPT_ROOT / "AI" / "Core.py"
INTELLECT_PATH = MOB_SCRIPT_ROOT / "AI" / "Intellect.py"
TRANSLATOR_PATH = MOB_SCRIPT_ROOT / "Combat" / "CommandTranslator.py"


def ReadMethod(PathValue, ClassName, MethodName):
    Tree = ast.parse(PathValue.read_text(encoding="utf-8-sig"))
    ClassNode = next(
        Node for Node in Tree.body
        if isinstance(Node, ast.ClassDef) and Node.name == ClassName
    )
    return next(
        Node for Node in ClassNode.body
        if isinstance(Node, ast.FunctionDef) and Node.name == MethodName
    )


def BuildHarness(Name, PathValue, SourceClassName, MethodNames, Namespace=None):
    Methods = [ReadMethod(PathValue, SourceClassName, MethodName) for MethodName in MethodNames]
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


class FakeController(object):
    def __init__(self, StateType, FinishState=True):
        self.StateType = StateType
        self.FinishState = FinishState

    def get_state_type(self):
        return self.StateType


class FakeDecision(object):
    def __init__(self, Skill, Score, Reason):
        self.skill = Skill
        self.score = Score
        self.reason = Reason


def Main():
    # Codex 2026-08-04: 攻击 CD 只限制低智力；中智力不靠续段特例绕过，并保持蓄力释放闭环。
    CoreHarness = BuildHarness(
        "CoreHarness",
        CORE_PATH,
        "MobAICore",
        (
            "attack_internal_cd_ready",
            "_should_hold_passive_charge",
            "_has_passive_charge_release_path",
            "_try_passive_charge_decision",
        ),
        {"time": time, "random": random, "AIDecision": FakeDecision},
    )
    Harness = CoreHarness()
    Harness.mob = ValueObject()
    Harness._is_attack_cd_skill = lambda Skill: True
    Harness._is_attack_cd_command = lambda Command: True
    Harness.attackInternalCooldownUntil = time.time() + 30.0
    IntellectModule = runpy.run_path(str(INTELLECT_PATH))
    LowPreset = IntellectModule["INTELLECT_PRESETS"][IntellectModule["INTELLECT_LOW"]]
    MidPreset = IntellectModule["INTELLECT_PRESETS"][IntellectModule["INTELLECT_MID"]]
    assert LowPreset["attackInternalCooldown"] > 0.0
    assert MidPreset["attackInternalCooldown"] == 0.0
    Harness._get_attack_internal_cd = lambda: LowPreset["attackInternalCooldown"]
    assert not Harness.attack_internal_cd_ready(ValueObject(skillId="common_attack"))
    Harness._get_attack_internal_cd = lambda: MidPreset["attackInternalCooldown"]
    assert Harness.attack_internal_cd_ready(ValueObject(skillId="common_attack"))

    Control = ValueObject(
        AllSwordSoul=False,
        AttackNeedSwordSoul=50.0,
        SwordSoulValue_MAX=100.0,
        SwordSoulValue=0.0,
    )
    Controller = FakeController("common_attack", True)
    Harness.mob = ValueObject(command_translator=Control, fight_controller=Controller)
    Harness.intellect = ValueObject(passiveChargeLevel2HoldChance=0.4)
    assert not Harness._should_hold_passive_charge(), "common attack recovery must not start passive charge"
    Controller.StateType = "none"
    assert Harness._should_hold_passive_charge(), "idle state should retain passive charge capability"
    Controller.StateType = "sneaking"
    assert Harness._should_hold_passive_charge(), "active charge should continue until resource is ready"

    ReleaseSkill = ValueObject(skillId="charge_release", stateId="fight_attack_first")
    Harness.skillCandidates = [ReleaseSkill]
    Harness.mob.HasFightState = lambda StateId: StateId in ("fight_attack_first", "fight_attack_sneaking_1")
    assert Harness._has_passive_charge_release_path()
    Harness.mob.HasFightState = lambda StateId: StateId == "fight_attack_first"
    assert not Harness._has_passive_charge_release_path()

    Controller.StateType = "sneaking"
    Harness.intellect.tacticPassiveCharge = True
    Harness._should_hold_passive_charge = lambda: False
    Harness._pick_passive_charge_release = lambda Usable: ReleaseSkill
    Harness.utilityEvaluator = ValueObject(
        targetReader=ValueObject(read=lambda Sense: (_ for _ in ()).throw(AssertionError("release checked too late")))
    )
    Decision = Harness._try_passive_charge_decision(ValueObject(), [ReleaseSkill])
    assert Decision.skill is ReleaseSkill and Decision.reason == "passive_charge_release"

    TranslatorHarness = BuildHarness(
        "TranslatorHarness",
        TRANSLATOR_PATH,
        "MobCommandTranslator",
        ("ExpressControlAttack",),
    )
    Translator = TranslatorHarness()
    ClearedTimers = []
    Translator._clear_timer = lambda Name: ClearedTimers.append(Name)
    Translator.ReadyAttack = False
    Translator.AttackState = "sneaking"
    assert Translator.ExpressControlAttack(False)
    assert ClearedTimers[:2] == ["LongPressAttack", "AutoReleaseCharge"], ClearedTimers
    assert Translator.AttackState == "none"
    print("iron golem combo/charge AI valid: attack_cd=low_only charge_entry=idle release=closed")


if __name__ == "__main__":
    Main()
