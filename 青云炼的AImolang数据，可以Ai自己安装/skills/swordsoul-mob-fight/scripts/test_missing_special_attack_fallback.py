# coding=utf-8
"""Mob 缺失特殊普攻状态时的基础平A降级回归。"""

import ast
import copy
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[4]
MOB_SCRIPT_ROOT = PROJECT_ROOT / "src" / "SwordSoul_NewERA_B" / "SwordSoulMobFightScripts"
TRANSLATOR_PATH = MOB_SCRIPT_ROOT / "Combat" / "CommandTranslator.py"
IRON_GOLEM_PATH = MOB_SCRIPT_ROOT / "Entities" / "IronGolemMob.py"


def ReadTree(PathValue):
    return ast.parse(PathValue.read_text(encoding="utf-8-sig"))


def BuildTranslatorHarness():
    Tree = ReadTree(TRANSLATOR_PATH)
    SourceClass = next(
        Node for Node in Tree.body
        if isinstance(Node, ast.ClassDef) and Node.name == "MobCommandTranslator"
    )
    RequiredNames = {
        "COMMON_ATTACK_SORT",
        "WEAPON_COMMON_ATTACK_SORT_MAP",
        "COMMON_ATTACK_STATE_ID_MAP",
        "updateCommonAttackState",
        "get_common_attack_sort",
        "clearCommonAttackState",
        "HasCommonAttackStage",
        "TryCommonAttackStage",
        "prepare_common_attack_state",
    }
    Body = []
    for Node in SourceClass.body:
        if isinstance(Node, ast.Assign):
            TargetNames = {
                Target.id for Target in Node.targets
                if isinstance(Target, ast.Name)
            }
            if TargetNames & RequiredNames:
                Body.append(copy.deepcopy(Node))
        elif isinstance(Node, ast.FunctionDef) and Node.name in RequiredNames:
            Body.append(copy.deepcopy(Node))
    HarnessClass = ast.ClassDef(
        name="TranslatorHarness",
        bases=[ast.Name(id="object", ctx=ast.Load())],
        keywords=[],
        body=Body,
        decorator_list=[],
    )
    Module = ast.fix_missing_locations(ast.Module(body=[HarnessClass], type_ignores=[]))
    Namespace = {"mob_trace": lambda *Args: None}
    exec(compile(Module, str(TRANSLATOR_PATH), "exec"), Namespace)
    return Namespace["TranslatorHarness"]


def ReadIronGolemAllowedStates():
    Tree = ReadTree(IRON_GOLEM_PATH)
    Assignment = next(
        Node for Node in Tree.body
        if isinstance(Node, ast.Assign)
        and any(
            isinstance(Target, ast.Name) and Target.id == "IRON_GOLEM_ALLOWED_STATE_IDS"
            for Target in Node.targets
        )
    )
    return ast.literal_eval(Assignment.value)


class FakeController(object):
    def __init__(self):
        self.StateId = "fight_none"

    def get_state_id(self):
        return self.StateId


class FakeMob(object):
    def __init__(self, AvailableStates):
        self.entityId = "iron-golem-test"
        self.WeaponType = "empty"
        self.fight_controller = FakeController()
        self.AvailableStates = set(AvailableStates)

    def HasFightState(self, StateId):
        return StateId in self.AvailableStates


def BuildControl(AvailableStates):
    Control = BuildTranslatorHarness()()
    Control.mob = FakeMob(AvailableStates)
    Control.TraceId = "missing-special-state"
    Control.CommonAttackState = None
    Control.ActionCommonAttackStateSort = []
    Control.UsingCommonAttackStateSort = []
    Control.PerfectDefenseState = False
    Control.InSecondJump = False
    Control.FastControlRisingDragon = False
    Control.IsSneaking = False
    Control.IsSprinting = False
    Control.BudgeSneaking = False
    Control.OnGround = True
    Control.RefreshNativeContext = lambda: Control.OnGround
    return Control


def Main():
    AllowedStates = ReadIronGolemAllowedStates()
    assert "fight_attack_up" not in AllowedStates
    assert "fight_attack_first" in AllowedStates
    assert "fight_attack_sprint" in AllowedStates

    # Codex 2026-08-04: 铁傀儡蹲地普攻缺少升龙时必须立即降级到基础平A，不能残留第18阶段。
    Control = BuildControl(AllowedStates)
    Control.IsSneaking = True
    assert Control.prepare_common_attack_state() == 1
    assert Control.CommonAttackState == 1

    # 旧运行时若已经留下第18阶段，下一次普通平A也必须自行恢复，无需先释放疾跑攻击。
    Control.IsSneaking = False
    Control.CommonAttackState = 18
    assert Control.prepare_common_attack_state() == 1
    assert Control.CommonAttackState == 1

    # 实体真实具备的特殊分支仍保持 SWS 原优先级，不受降级逻辑影响。
    Control.IsSprinting = True
    assert Control.prepare_common_attack_state() == 16
    assert Control.CommonAttackState == 16

    print("missing special attack fallback valid: crouch->basic stale18->basic sprint->16")


if __name__ == "__main__":
    Main()
