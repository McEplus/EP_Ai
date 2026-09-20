# coding=utf-8
"""生物战斗拳风与 SWS 原始实现的静态同步回归检查。"""

import ast
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[4]
BEHAVIOR_ROOT = PROJECT_ROOT / "src" / "SwordSoul_NewERA_B"
SWS_STATE_PATH = BEHAVIOR_ROOT / "SwordSoulFightScripts" / "FightSystem" / "UseEmptyState.py"
MOB_STATE_PATH = BEHAVIOR_ROOT / "SwordSoulMobFightScripts" / "Entities" / "FightState" / "UseEmptyState.py"
MOB_FIGHT_STATE_SYSTEM_PATH = BEHAVIOR_ROOT / "SwordSoulMobFightScripts" / "Combat" / "FightStateSystem.py"
SWS_EFFECT_PATH = BEHAVIOR_ROOT / "SwordSoulFightScripts" / "EffectSystem" / "Fight.py"
MOB_RENDER_PATH = BEHAVIOR_ROOT / "SwordSoulMobFightScripts" / "Render" / "MobRenderClient.py"
PUNCH_METHODS = {"PlayPunchAirFlow", "PlayPunchSonicBoom"}


def ReadTree(PathValue):
    return ast.parse(PathValue.read_text(encoding="utf-8-sig"))


def DecoratedStateId(ClassNode):
    for Decorator in ClassNode.decorator_list:
        if not isinstance(Decorator, ast.Call) or not isinstance(Decorator.func, ast.Attribute):
            continue
        if Decorator.func.attr != "BindState" or len(Decorator.args) < 2:
            continue
        try:
            StateId = ast.literal_eval(Decorator.args[0])
            StateType = ast.literal_eval(Decorator.args[1])
        except (ValueError, TypeError):
            continue
        if StateType == "empty":
            return StateId
    return None


def MobClassName(StateId):
    Parts = StateId.replace("fight_", "", 1).split("_")
    return "Empty" + "".join(Part[:1].upper() + Part[1:] for Part in Parts)


def PunchTimerCalls(ClassNode):
    Result = []
    for Node in ast.walk(ClassNode):
        if not isinstance(Node, ast.Call) or not isinstance(Node.func, ast.Attribute):
            continue
        if Node.func.attr != "StateAnim_CreateTimer" or len(Node.args) < 2:
            continue
        Callback = Node.args[1]
        if not isinstance(Callback, ast.Name) or Callback.id not in PUNCH_METHODS:
            continue
        Result.append((Node.lineno, ast.dump(ast.Tuple(elts=Node.args, ctx=ast.Load()))))
    return [Value for _, Value in sorted(Result)]


def AssertStateCallsMatch():
    SwsTree = ReadTree(SWS_STATE_PATH)
    MobTree = ReadTree(MOB_STATE_PATH)
    MobClasses = dict(
        (Node.name, Node) for Node in MobTree.body
        if isinstance(Node, ast.ClassDef)
    )
    PunchCallCount = 0
    PunchStateCount = 0
    for SwsClass in SwsTree.body:
        if not isinstance(SwsClass, ast.ClassDef):
            continue
        StateId = DecoratedStateId(SwsClass)
        SwsCalls = PunchTimerCalls(SwsClass)
        if not StateId or not SwsCalls:
            continue
        ExpectedMobClass = MobClassName(StateId)
        assert ExpectedMobClass in MobClasses, (StateId, ExpectedMobClass)
        MobCalls = PunchTimerCalls(MobClasses[ExpectedMobClass])
        assert MobCalls == SwsCalls, "punch timer drift: %s" % StateId
        PunchCallCount += len(SwsCalls)
        PunchStateCount += 1
    assert PunchCallCount == 32, PunchCallCount
    assert PunchStateCount == 16, PunchStateCount
    return PunchStateCount, PunchCallCount


def FindClass(Tree, ClassName):
    return next(
        Node for Node in Tree.body
        if isinstance(Node, ast.ClassDef) and Node.name == ClassName
    )


def FindMethod(ClassNode, MethodName):
    return next(
        Node for Node in ClassNode.body
        if isinstance(Node, ast.FunctionDef) and Node.name == MethodName
    )


def AssertSwsPublicMethodsSupportLocalCreation():
    EffectClass = FindClass(ReadTree(SWS_EFFECT_PATH), "AttackEffectSystem")
    for MethodName in ("PunchAirFlow", "PunchSonicBoom"):
        Method = FindMethod(EffectClass, MethodName)
        assert Method.args.args[-1].arg == "AllClient", MethodName
        assert isinstance(Method.args.defaults[-1], ast.Constant)
        assert Method.args.defaults[-1].value is True
        CreateCalls = [
            Node for Node in ast.walk(Method)
            if isinstance(Node, ast.Call)
            and isinstance(Node.func, ast.Attribute)
            and Node.func.attr == "CreateSuperEffect"
        ]
        assert len(CreateCalls) == 1, MethodName
        # Codex 2026-08-05: 质量元数据可追加在 AllClient 后，按 CreateSuperEffect 固定签名位置核对本地开关。
        assert len(CreateCalls[0].args) > 13, MethodName
        AllClientArgument = CreateCalls[0].args[13]
        assert isinstance(AllClientArgument, ast.Name) and AllClientArgument.id == "AllClient", MethodName


def AssertMobPunchOwnership():
    MobStateTree = ReadTree(MOB_STATE_PATH)
    for HelperName, EffectMethodName in (
        ("PlayPunchAirFlow", "PunchAirFlow"),
        ("PlayPunchSonicBoom", "PunchSonicBoom"),
    ):
        Helper = next(
            Node for Node in MobStateTree.body
            if isinstance(Node, ast.FunctionDef) and Node.name == HelperName
        )
        GetComponentCalls = [
            Node for Node in ast.walk(Helper)
            if isinstance(Node, ast.Call)
            and isinstance(Node.func, ast.Attribute)
            and Node.func.attr == "GetComponent"
        ]
        assert len(GetComponentCalls) == 1, HelperName
        GetComponentOwner = GetComponentCalls[0].func.value
        assert isinstance(GetComponentOwner, ast.Name) and GetComponentOwner.id == "StateObj", HelperName
        EffectCalls = [
            Node for Node in ast.walk(Helper)
            if isinstance(Node, ast.Call)
            and isinstance(Node.func, ast.Attribute)
            and Node.func.attr == EffectMethodName
        ]
        assert len(EffectCalls) == 1, HelperName
        EntityArgument = EffectCalls[0].args[0]
        assert isinstance(EntityArgument, ast.Attribute), HelperName
        assert isinstance(EntityArgument.value, ast.Name) and EntityArgument.value.id == "StateObj", HelperName
        assert EntityArgument.attr == "playerId", HelperName

    FightStateClass = FindClass(ReadTree(MOB_FIGHT_STATE_SYSTEM_PATH), "MobFightState")
    NormalizeMethod = FindMethod(FightStateClass, "_normalize_sws_component_args")
    StateOwnershipAssignments = [
        Node for Node in ast.walk(NormalizeMethod)
        if isinstance(Node, ast.Assign)
        and any(
            isinstance(Target, ast.Subscript)
            and isinstance(Target.value, ast.Name)
            and Target.value.id == "args"
            and isinstance(Target.slice, ast.Constant)
            and Target.slice.value == 0
            for Target in Node.targets
        )
        and isinstance(Node.value, ast.Attribute)
        and isinstance(Node.value.value, ast.Name)
        and Node.value.value.id == "self"
        and Node.value.attr == "playerId"
    ]
    assert StateOwnershipAssignments, "missing server punch ownership override"

    RenderClass = FindClass(ReadTree(MOB_RENDER_PATH), "MobFightRenderSystem")
    RenderMethod = FindMethod(RenderClass, "_play_sws_punch_effect_local")
    EventOwnershipAssignments = [
        Node for Node in ast.walk(RenderMethod)
        if isinstance(Node, ast.Assign)
        and any(
            isinstance(Target, ast.Subscript)
            and isinstance(Target.value, ast.Name)
            and Target.value.id == "args"
            and isinstance(Target.slice, ast.Constant)
            and Target.slice.value == 0
            for Target in Node.targets
        )
        and isinstance(Node.value, ast.Name)
        and Node.value.id == "entityId"
    ]
    assert len(EventOwnershipAssignments) == 1, "missing client event ownership override"


def AssertMobUsesSwsPublicMethods():
    RenderText = MOB_RENDER_PATH.read_text(encoding="utf-8")
    RenderClass = FindClass(ReadTree(MOB_RENDER_PATH), "MobFightRenderSystem")
    MethodNames = {
        Node.name for Node in RenderClass.body
        if isinstance(Node, ast.FunctionDef)
    }
    assert "_play_localized_punch_air_flow" not in MethodNames
    assert "_play_localized_punch_sonic_boom" not in MethodNames
    assert "_normalize_punch_effect_args" not in MethodNames
    assert "_call_sws_public_effect_local" in MethodNames
    assert '{"AllClient": False}' in RenderText
    assert 'GetVaryingClient("OtherPlayerEffect"' in RenderText
    assert 'SetVaryingClient("OtherPlayerEffect", True)' in RenderText
    assert 'SetVaryingClient("OtherPlayerEffect", oldOtherPlayerEffect)' in RenderText


def Main():
    # Codex 2026-08-03: 固化 SWS 招式参数、公开特效入口及 Mob 单端执行三层契约，防止后续再次分叉。
    PunchStateCount, PunchCallCount = AssertStateCallsMatch()
    AssertSwsPublicMethodsSupportLocalCreation()
    AssertMobPunchOwnership()
    AssertMobUsesSwsPublicMethods()
    print(
        "mob punch effect sync valid: states=%d timer_calls=%d public_methods=2 ownership_guards=3"
        % (PunchStateCount, PunchCallCount)
    )


if __name__ == "__main__":
    Main()
