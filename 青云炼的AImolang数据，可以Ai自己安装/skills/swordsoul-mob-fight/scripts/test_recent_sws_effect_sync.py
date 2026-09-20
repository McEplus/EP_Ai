# coding=utf-8
"""近期 SWS Sprint/Dodge 尘土调用到 Mob 调度桥的全量同步回归。"""

import ast
import copy
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[4]
BEHAVIOR_ROOT = PROJECT_ROOT / "src" / "SwordSoul_NewERA_B"
SWS_STATE_ROOT = BEHAVIOR_ROOT / "SwordSoulFightScripts" / "FightSystem"
MOB_ROOT = BEHAVIOR_ROOT / "SwordSoulMobFightScripts"
MOB_STATE_ROOT = MOB_ROOT / "Entities" / "FightState"
SCHEDULE_PATH = MOB_ROOT / "Combat" / "SWSRecentEffectSchedule.py"
FIGHT_STATE_SYSTEM_PATH = MOB_ROOT / "Combat" / "FightStateSystem.py"
FIGHT_CONTROLLER_PATH = MOB_ROOT / "Combat" / "FightController.py"
MOB_RENDER_PATH = MOB_ROOT / "Render" / "MobRenderClient.py"
MOVEMENT_EFFECT_METHODS = {"SprintDirtSmoke", "DodgeDirtSmoke"}
SOURCE_PAIRS = (
    ("CommonState.py", "common"),
    ("UseDaggerState.py", "dagger"),
    ("UseDoubleKnifeState.py", "double_knife"),
    ("UseEmptyState.py", "empty"),
    ("UseEpeeState.py", "epee"),
    ("UseKatanaState.py", "katana"),
    ("UseKnifeState.py", "knife"),
    ("UseMacheteState.py", "machete"),
    ("UsePikeState.py", "pike"),
    ("UseSickleState.py", "sickle"),
    ("UseStickState.py", "stick"),
)


def ReadTree(PathValue):
    return ast.parse(PathValue.read_text(encoding="utf-8-sig"))


def DecoratedStateId(ClassNode):
    for Decorator in ClassNode.decorator_list:
        if not isinstance(Decorator, ast.Call) or not isinstance(Decorator.func, ast.Attribute):
            continue
        if Decorator.func.attr not in ("BindState", "BindSkillState") or not Decorator.args:
            continue
        try:
            return ast.literal_eval(Decorator.args[0])
        except (ValueError, TypeError):
            continue
    return None


def ExtractMovementSchedule(PathValue):
    Result = {}
    for ClassNode in ReadTree(PathValue).body:
        if not isinstance(ClassNode, ast.ClassDef):
            continue
        StateId = DecoratedStateId(ClassNode)
        if not StateId:
            continue
        Actions = []
        for Node in ast.walk(ClassNode):
            if not isinstance(Node, ast.Call) or not isinstance(Node.func, ast.Attribute):
                continue
            if Node.func.attr in MOVEMENT_EFFECT_METHODS:
                EffectArgs = tuple(ast.literal_eval(Argument) for Argument in Node.args[1:])
                Actions.append((Node.lineno, 0.0, Node.func.attr, EffectArgs))
                continue
            if Node.func.attr != "StateAnim_CreateTimer" or len(Node.args) < 4:
                continue
            Callback = Node.args[1]
            if not isinstance(Callback, ast.Attribute) or Callback.attr not in MOVEMENT_EFFECT_METHODS:
                continue
            Delay = ast.literal_eval(Node.args[0])
            EffectArgs = tuple(ast.literal_eval(Argument) for Argument in Node.args[4:])
            Actions.append((Node.lineno, Delay, Callback.attr, EffectArgs))
        if Actions:
            Result[StateId] = tuple(
                (Delay, MethodName, EffectArgs)
                for _, Delay, MethodName, EffectArgs in sorted(Actions)
            )
    return Result


def ReadSchedule():
    Tree = ReadTree(SCHEDULE_PATH)
    Assignment = next(
        Node for Node in Tree.body
        if isinstance(Node, ast.Assign)
        and any(isinstance(Target, ast.Name) and Target.id == "SWS_RECENT_MOVEMENT_EFFECT_SCHEDULE" for Target in Node.targets)
    )
    CountAssignment = next(
        Node for Node in Tree.body
        if isinstance(Node, ast.Assign)
        and any(isinstance(Target, ast.Name) and Target.id == "SWS_RECENT_MOVEMENT_EFFECT_CALL_COUNT" for Target in Node.targets)
    )
    return ast.literal_eval(Assignment.value), ast.literal_eval(CountAssignment.value)


def AssertScheduleMatchesSws():
    Expected = dict(
        (WeaponType, ExtractMovementSchedule(SWS_STATE_ROOT / FileName))
        for FileName, WeaponType in SOURCE_PAIRS
    )
    Actual, DeclaredCount = ReadSchedule()
    assert Actual == Expected
    ActualCount = sum(len(Actions) for StateMap in Actual.values() for Actions in StateMap.values())
    assert ActualCount == DeclaredCount == 84, (ActualCount, DeclaredCount)
    assert sum(len(StateMap) for StateMap in Actual.values()) == 55
    return len(Actual), ActualCount


def AssertUnsupportedBowIsExplicit():
    BowSchedule = ExtractMovementSchedule(SWS_STATE_ROOT / "UseBowState.py")
    BowCallCount = sum(len(Actions) for Actions in BowSchedule.values())
    assert BowCallCount == 6, BowCallCount
    assert not (MOB_STATE_ROOT / "UseBowState.py").exists()
    return BowCallCount


def AssertNoDuplicateMobStateCalls():
    CallCount = 0
    for PathValue in MOB_STATE_ROOT.glob("Use*State.py"):
        for Node in ast.walk(ReadTree(PathValue)):
            if not isinstance(Node, ast.Call) or not isinstance(Node.func, ast.Attribute):
                continue
            if Node.func.attr in MOVEMENT_EFFECT_METHODS:
                CallCount += 1
            elif Node.func.attr == "StateAnim_CreateTimer" and len(Node.args) > 1:
                Callback = Node.args[1]
                if isinstance(Callback, ast.Attribute) and Callback.attr in MOVEMENT_EFFECT_METHODS:
                    CallCount += 1
    assert CallCount == 0, "movement dirt smoke would play twice: %d" % CallCount


def BuildScheduleHarness(Schedule):
    StateSystemTree = ReadTree(FIGHT_STATE_SYSTEM_PATH)
    StateClass = next(
        Node for Node in StateSystemTree.body
        if isinstance(Node, ast.ClassDef) and Node.name == "MobFightState"
    )
    ScheduleMethod = next(
        copy.deepcopy(Node) for Node in StateClass.body
        if isinstance(Node, ast.FunctionDef) and Node.name == "ScheduleSWSRecentMovementEffects"
    )
    HarnessClass = ast.ClassDef(
        name="ScheduleHarness",
        bases=[ast.Name(id="object", ctx=ast.Load())],
        keywords=[],
        body=[ScheduleMethod],
        decorator_list=[],
    )
    HarnessModule = ast.fix_missing_locations(ast.Module(body=[HarnessClass], type_ignores=[]))
    Namespace = {"SWS_RECENT_MOVEMENT_EFFECT_SCHEDULE": Schedule}
    exec(compile(HarnessModule, str(FIGHT_STATE_SYSTEM_PATH), "exec"), Namespace)
    return Namespace["ScheduleHarness"]


def AssertRuntimeSchedulingUsesCurrentMob():
    Schedule, _ = ReadSchedule()
    HarnessClass = BuildScheduleHarness(Schedule)

    DirectHarness = HarnessClass()
    DirectHarness.State_Effect = True
    DirectHarness.StateId = "fight_dodge_forward"
    DirectHarness.WeaponType = "empty"
    DirectHarness.playerId = "mob-entity"
    DirectHarness.DirectCalls = []
    DirectHarness.TimerCalls = []
    DirectHarness.PlaySwordSoulEffect = lambda *Args: DirectHarness.DirectCalls.append(Args)
    DirectHarness.StateAnim_CreateTimer = lambda *Args: DirectHarness.TimerCalls.append(Args)
    assert DirectHarness.ScheduleSWSRecentMovementEffects() == 1
    assert DirectHarness.DirectCalls == [
        ("AttackEffectSystem", "DodgeDirtSmoke", ["mob-entity", "root", (0, 0, 0), (0, 0, 0), 0.4])
    ]
    assert DirectHarness.TimerCalls == []

    # Codex 2026-08-07: 逐武器确认 Mob 疾跑攻击全部排除自动同步尘土。
    SprintWeaponTypes = sorted(
        WeaponType for WeaponType, StateMap in Schedule.items()
        if "fight_attack_sprint" in StateMap
    )
    assert len(SprintWeaponTypes) == 10
    for WeaponType in SprintWeaponTypes:
        TimerHarness = HarnessClass()
        TimerHarness.State_Effect = True
        TimerHarness.StateId = "fight_attack_sprint"
        TimerHarness.WeaponType = WeaponType
        TimerHarness.playerId = "mob-entity"
        TimerHarness.DirectCalls = []
        TimerHarness.TimerCalls = []
        TimerHarness.PlaySwordSoulEffect = lambda *Args: TimerHarness.DirectCalls.append(Args)
        TimerHarness.StateAnim_CreateTimer = lambda *Args: TimerHarness.TimerCalls.append(Args)
        assert TimerHarness.ScheduleSWSRecentMovementEffects() == 0, WeaponType
        assert TimerHarness.DirectCalls == [], WeaponType
        assert TimerHarness.TimerCalls == [], WeaponType


def AssertBridgeLifecycle():
    StateSystemText = FIGHT_STATE_SYSTEM_PATH.read_text(encoding="utf-8")
    ControllerText = FIGHT_CONTROLLER_PATH.read_text(encoding="utf-8")
    RenderText = MOB_RENDER_PATH.read_text(encoding="utf-8")
    assert "def ScheduleSWSRecentMovementEffects(self):" in StateSystemText
    assert 'if self.StateId == "fight_attack_sprint":' in StateSystemText
    assert 'SWS_RECENT_MOVEMENT_EFFECT_SCHEDULE.get("common"' in StateSystemText
    assert 'args = [self.playerId] + list(effectArgs)' in StateSystemText
    assert 'methodName in ("SprintDirtSmoke", "DodgeDirtSmoke", "StopSprintDirtSmoke", "StopDodgeDirtSmoke")' in StateSystemText
    # Codex 2026-08-07: 状态总入口禁止自动注入尘土，调度助手只能由具体招式显式使用。
    assert "stateObj.ScheduleSWSRecentMovementEffects()" not in ControllerText
    assert 'stateObj.PlaySwordSoulEffect("AttackEffectSystem", "StopSprintDirtSmoke", [entityId])' in ControllerText
    assert 'stateObj.PlaySwordSoulEffect("AttackEffectSystem", "StopDodgeDirtSmoke", [entityId])' in ControllerText
    assert 'if methodName in ("StopSprintDirtSmoke", "StopDodgeDirtSmoke"):' in RenderText
    assert 'return self._call_sws_component_local("AttackEffectSystem", EffectMethod, [entityId])' in RenderText


def Main():
    # Codex 2026-08-03: 用 SWS 当前源状态直接校验 Mob 调度表、单端桥接和退出清理，禁止后续静默漏同步。
    WeaponCount, CallCount = AssertScheduleMatchesSws()
    BowCallCount = AssertUnsupportedBowIsExplicit()
    AssertNoDuplicateMobStateCalls()
    AssertRuntimeSchedulingUsesCurrentMob()
    AssertBridgeLifecycle()
    print(
        "recent SWS effect sync valid: weapon_groups=%d synced_calls=%d unsupported_bow_calls=%d"
        % (WeaponCount, CallCount, BowCallCount)
    )


if __name__ == "__main__":
    Main()
