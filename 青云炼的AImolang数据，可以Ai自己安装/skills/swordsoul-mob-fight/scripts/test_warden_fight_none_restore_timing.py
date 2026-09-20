# coding=utf-8
"""监守者招式归零后立即退出软战斗模式并恢复原版追踪的回归。"""

import ast
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[4]
MOB_ROOT = PROJECT_ROOT / "src" / "SwordSoul_NewERA_B" / "SwordSoulMobFightScripts"
BASE_PATH = MOB_ROOT / "Entities" / "BaseMob.py"
WARDEN_PATH = MOB_ROOT / "Entities" / "WardenMob.py"


def ReadClass(PathValue, ClassName):
    Tree = ast.parse(PathValue.read_text(encoding="utf-8-sig"), str(PathValue))
    return [
        Node for Node in Tree.body
        if isinstance(Node, ast.ClassDef) and Node.name == ClassName
    ][-1]


def ReadAssignments(ClassNode):
    Result = {}
    for Node in ClassNode.body:
        if not isinstance(Node, ast.Assign) or len(Node.targets) != 1:
            continue
        Target = Node.targets[0]
        if isinstance(Target, ast.Name):
            try:
                Result[Target.id] = ast.literal_eval(Node.value)
            except (ValueError, TypeError):
                pass
    return Result


def BuildHarness():
    BaseClass = ReadClass(BASE_PATH, "SwordSoulMobEntity")
    Names = {
        "_has_active_target",
        "_active_target_holds_fight_mode",
        "on_fight_state_changed",
    }
    Methods = [
        Node for Node in BaseClass.body
        if isinstance(Node, ast.FunctionDef) and Node.name in Names
    ]
    HarnessNode = ast.ClassDef(
        name="Harness",
        bases=[ast.Name(id="object", ctx=ast.Load())],
        keywords=[],
        body=Methods,
        decorator_list=[],
    )
    ModuleNode = ast.Module(body=[HarnessNode], type_ignores=[])
    ast.fix_missing_locations(ModuleNode)
    Namespace = {}
    exec(compile(ModuleNode, str(BASE_PATH), "exec"), Namespace)
    return Namespace["Harness"]


class ValueObject(object):
    def __init__(self, **Values):
        self.__dict__.update(Values)


def Main():
    WardenAssignments = ReadAssignments(ReadClass(WARDEN_PATH, "WardenMob"))
    assert WardenAssignments["ActiveTargetHoldsFightMode"] is False
    assert WardenAssignments["PassiveSoftFightHoldEnabled"] is False
    assert WardenAssignments["ExitFightModeOnStateNone"] is True

    BaseSource = BASE_PATH.read_text(encoding="utf-8-sig")
    assert BaseSource.count("active or self._active_target_holds_fight_mode()") == 1
    assert BaseSource.count("and not self._active_target_holds_fight_mode()") == 1
    assert BaseSource.count("not self.PassiveSoftFightHoldEnabled") == 2

    Calls = []
    Mob = BuildHarness()()
    Mob.ActiveTargetHoldsFightMode = False
    Mob.ExitFightModeOnStateNone = True
    Mob.pending_fight_request = None
    Mob.sense = ValueObject(entitySense=ValueObject(hasTarget=True, targetInLoseRange=False))
    Mob.command_translator = ValueObject(has_active_command=lambda: False)
    Mob.set_soft_switch = lambda Enabled: Calls.append(Enabled) or True

    # 目标仍存在也不能单独把监守者锁在 FIGHT；招式归零必须立即关闭软开关。
    assert Mob._has_active_target() is True
    assert Mob._active_target_holds_fight_mode() is False
    assert Mob.on_fight_state_changed("fight_attack_first", "fight_none") is True
    assert Calls == [False]

    # 连段请求或真实按住的输入仍应保持本轮战斗，不能在中间错误恢复组件。
    Mob.pending_fight_request = {"state_id": "fight_attack_second"}
    assert Mob.on_fight_state_changed("fight_attack_first", "fight_none") is False
    Mob.pending_fight_request = None
    Mob.command_translator = ValueObject(has_active_command=lambda: True)
    assert Mob.on_fight_state_changed("fight_attack_first", "fight_none") is False
    assert Calls == [False]

    print("warden fight_none restore timing checks passed: cases=6")


if __name__ == "__main__":
    Main()
