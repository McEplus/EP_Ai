# coding=utf-8
"""不死斩/裂空审判从当前 SWS 到 Mob 渲染桥的同步回归。"""

import ast
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[4]
BEHAVIOR_ROOT = PROJECT_ROOT / "src" / "SwordSoul_NewERA_B"
SWS_KATANA_PATH = BEHAVIOR_ROOT / "SwordSoulFightScripts" / "FightSystem" / "UseKatanaState.py"
SWS_EFFECT_PATH = BEHAVIOR_ROOT / "SwordSoulFightScripts" / "EffectSystem" / "Fight.py"
MOB_KATANA_PATH = BEHAVIOR_ROOT / "SwordSoulMobFightScripts" / "Entities" / "FightState" / "UseKatanaState.py"
MOB_RENDER_PATH = BEHAVIOR_ROOT / "SwordSoulMobFightScripts" / "Render" / "MobRenderClient.py"

DIMENSIONAL_EFFECT_METHODS = {
    "SetPostState",
    "playParticle",
    "DirtSmoke",
    "SetDirtParticleTimeStop",
    "DimensionalSeverRound",
    "DimensionalSeverSmoke",
    "DimensionalSeverSlash",
    "DimensionalSeverGlass",
    "BeginDimensionalSeverDistortion",
    "GrayScreen",
    "DistortPower",
    "ShootPower",
}
UNDEAD_EFFECT_METHODS = {"UndeadVortex", "UndeadSmoke"}


def ReadTree(PathValue):
    return ast.parse(PathValue.read_text(encoding="utf-8-sig"))


def FindClass(Tree, Name):
    return next(Node for Node in Tree.body if isinstance(Node, ast.ClassDef) and Node.name == Name)


def FindMethod(ClassNode, Name):
    return next(Node for Node in ClassNode.body if isinstance(Node, ast.FunctionDef) and Node.name == Name)


def NormalizeValue(Node):
    if isinstance(Node, ast.Name) and Node.id == "playerId":
        return "<entity>"
    if isinstance(Node, ast.Attribute) and isinstance(Node.value, ast.Name) and Node.value.id == "Quality":
        # Codex 2026-08-10: 状态配置可使用质量常量，比较同步调用时还原为其运行时整数值。
        return {
            "QUALITY_LOW": 0,
            "QUALITY_MEDIUM": 1,
            "QUALITY_HIGH": 2,
        }[Node.attr]
    if (
        isinstance(Node, ast.Attribute)
        and Node.attr == "playerId"
        and isinstance(Node.value, ast.Name)
        and Node.value.id == "self"
    ):
        return "<entity>"
    if isinstance(Node, ast.Tuple):
        return tuple(NormalizeValue(Item) for Item in Node.elts)
    if isinstance(Node, ast.List):
        return [NormalizeValue(Item) for Item in Node.elts]
    if isinstance(Node, ast.Dict):
        return dict((NormalizeValue(Key), NormalizeValue(Value)) for Key, Value in zip(Node.keys, Node.values))
    return ast.literal_eval(Node)


CALL_PARAMETER_ORDER = {
    "playParticle": (
        "particle", "entityId", "locator", "offset", "rotate", "Time",
        "QualityCategory", "RequiredQuality", "EffectKey", "DensityStride",
    ),
}

CALL_PARAMETER_DEFAULTS = {
    "playParticle": {
        "locator": "",
        "offset": (0, 0, 0),
        "rotate": (0, 0, 0),
        "Time": 0.0,
        "QualityCategory": "skill",
        "RequiredQuality": 0,
        "EffectKey": "",
        "DensityStride": (1, 1, 1),
    },
}


def NormalizeCallArguments(CallName, Args, Keywords):
    ParameterOrder = CALL_PARAMETER_ORDER.get(CallName)
    if not ParameterOrder:
        return (
            tuple(NormalizeValue(Arg) for Arg in Args),
            tuple(sorted((Keyword.arg, NormalizeValue(Keyword.value)) for Keyword in Keywords)),
        )
    # Codex 2026-08-05: Compare keyword and positional bridge calls by their effective values.
    Values = dict(CALL_PARAMETER_DEFAULTS.get(CallName, {}))
    for Index, Arg in enumerate(Args):
        Values[ParameterOrder[Index]] = NormalizeValue(Arg)
    for Keyword in Keywords:
        Values[Keyword.arg] = NormalizeValue(Keyword.value)
    return tuple((Name, Values[Name]) for Name in ParameterOrder if Name in Values)


def ExtractEffectCalls(MethodNode, MethodNames):
    Calls = []
    for Node in ast.walk(MethodNode):
        if not isinstance(Node, ast.Call):
            continue
        if isinstance(Node.func, ast.Attribute):
            CallName = Node.func.attr
        elif isinstance(Node.func, ast.Name):
            CallName = Node.func.id
        else:
            continue
        if CallName == "StateAnim_CreateTimer" and len(Node.args) >= 3:
            Callback = Node.args[1]
            CallbackName = Callback.attr if isinstance(Callback, ast.Attribute) else (
                Callback.id if isinstance(Callback, ast.Name) else ""
            )
            if CallbackName in MethodNames:
                Calls.append((
                    Node.lineno,
                    NormalizeValue(Node.args[0]),
                    CallbackName,
                    NormalizeCallArguments(CallbackName, Node.args[3:], ()),
                ))
        elif CallName in MethodNames:
            Calls.append((
                Node.lineno,
                0.0,
                CallName,
                NormalizeCallArguments(CallName, Node.args, Node.keywords),
            ))
    return tuple((Delay, MethodName, Args) for _, Delay, MethodName, Args in sorted(Calls))


def ExtractAssignedLiteral(ClassNode, Name):
    for Node in ast.walk(ClassNode):
        if not isinstance(Node, ast.Assign):
            continue
        if any(isinstance(Target, ast.Name) and Target.id == Name for Target in Node.targets):
            return ast.literal_eval(Node.value)
    raise AssertionError("assignment missing: %s.%s" % (ClassNode.name, Name))


def ExtractSwsTrailBinderActions(MethodNode):
    Actions = []
    for Node in ast.walk(MethodNode):
        if not isinstance(Node, ast.Call) or not isinstance(Node.func, ast.Attribute):
            continue
        if Node.func.attr != "StateAnim_CreateTimer" or len(Node.args) < 2:
            continue
        Callback = Node.args[1]
        if not isinstance(Callback, ast.Attribute) or Callback.attr not in ("createBinder", "removeBinder"):
            continue
        Actions.append((Node.lineno, NormalizeValue(Node.args[0]), Callback.attr))
    return tuple((Delay, Action) for _, Delay, Action in sorted(Actions))


def ExtractMobTrailBinderActions(MethodNode):
    Actions = []
    for Node in ast.walk(MethodNode):
        if not isinstance(Node, ast.Call) or not isinstance(Node.func, ast.Attribute):
            continue
        if Node.func.attr != "StateAnim_CreateTimer" or len(Node.args) < 5:
            continue
        Callback = Node.args[1]
        if not isinstance(Callback, ast.Attribute) or Callback.attr != "PlayMobRenderAction":
            continue
        if NormalizeValue(Node.args[3]) != "trail":
            continue
        PayloadNode = Node.args[4]
        if not isinstance(PayloadNode, ast.Dict):
            continue
        Action = next(
            NormalizeValue(Value)
            for Key, Value in zip(PayloadNode.keys, PayloadNode.values)
            if NormalizeValue(Key) == "action"
        )
        Actions.append((Node.lineno, NormalizeValue(Node.args[0]), Action))
    return tuple((Delay, Action) for _, Delay, Action in sorted(Actions))


def AssertStateEffectsMatch():
    SwsTree = ReadTree(SWS_KATANA_PATH)
    MobTree = ReadTree(MOB_KATANA_PATH)
    SwsUndead = FindClass(SwsTree, "UndeadSlash")
    MobUndead = FindClass(MobTree, "KatanaSkillUndeadSlash")
    SwsDimensional = FindClass(SwsTree, "DimensionalSever")
    MobDimensional = FindClass(MobTree, "KatanaSkillDimensionalSever")

    # Codex 2026-08-03: 刀光材质、粒子层与寿命/间距必须直接等于当前 SWS 配置。
    assert ExtractAssignedLiteral(SwsUndead, "NewRightData") == ExtractAssignedLiteral(MobUndead, "NewRightData")
    assert ExtractEffectCalls(FindMethod(SwsUndead, "onStart"), UNDEAD_EFFECT_METHODS) == ExtractEffectCalls(
        FindMethod(MobUndead, "onStart"), UNDEAD_EFFECT_METHODS
    )
    assert ExtractSwsTrailBinderActions(FindMethod(SwsUndead, "onStart")) == (
        (0.7, "createBinder"),
        (1.15, "removeBinder"),
        (2.8, "createBinder"),
        (3.2, "removeBinder"),
    )
    assert ExtractMobTrailBinderActions(FindMethod(MobUndead, "onStart")) == (
        (0.7, "create_binder"),
        (1.15, "remove_binder"),
        (2.8, "create_binder"),
        (3.2, "remove_binder"),
    )

    assert ExtractEffectCalls(FindMethod(SwsDimensional, "onStart"), DIMENSIONAL_EFFECT_METHODS) == ExtractEffectCalls(
        FindMethod(MobDimensional, "onStart"), DIMENSIONAL_EFFECT_METHODS
    )
    assert ExtractEffectCalls(FindMethod(SwsDimensional, "BeginDimensionalSeverDistortion"), {"DimensionalSeverLightning"}) == ExtractEffectCalls(
        FindMethod(MobDimensional, "BeginDimensionalSeverDistortion"), {"DimensionalSeverLightning"}
    )
    assert ExtractEffectCalls(FindMethod(SwsDimensional, "onEnd"), {"SetDirtParticleTimeStop"}) == ExtractEffectCalls(
        FindMethod(MobDimensional, "onEnd"), {"SetDirtParticleTimeStop"}
    )


def AssertSwsLocalOnlySwitches():
    EffectTree = ReadTree(SWS_EFFECT_PATH)
    SkillEffectClass = FindClass(EffectTree, "SkillEffectSystem")
    for MethodName in ("UndeadVortex", "UndeadSmoke", "DimensionalSeverRound", "DimensionalSeverGlass", "BlackHoleCore"):
        MethodNode = FindMethod(SkillEffectClass, MethodName)
        assert MethodNode.args.args[-1].arg == "AllClient"
        assert isinstance(MethodNode.args.defaults[-1], ast.Constant) and MethodNode.args.defaults[-1].value is True
        CreateCalls = [
            Node for Node in ast.walk(MethodNode)
            if isinstance(Node, ast.Call) and isinstance(Node.func, ast.Attribute) and Node.func.attr == "CreateSuperEffect"
        ]
        assert len(CreateCalls) == 1
        assert isinstance(CreateCalls[0].args[13], ast.Name) and CreateCalls[0].args[13].id == "AllClient"


def AssertBlackHolePostLifecycle():
    EffectText = SWS_EFFECT_PATH.read_text(encoding="utf-8-sig")
    SkillEffectClass = FindClass(ast.parse(EffectText), "SkillEffectSystem")
    CoreMethod = FindMethod(SkillEffectClass, "BlackHoleCore")
    CreateCalls = [
        Node for Node in ast.walk(CoreMethod)
        if isinstance(Node, ast.Call) and isinstance(Node.func, ast.Attribute) and Node.func.attr == "CreateSuperEffect"
    ]
    assert len(CreateCalls) == 1
    assert isinstance(CreateCalls[0].args[12], ast.Constant) and CreateCalls[0].args[12].value == ""
    assert isinstance(CreateCalls[0].args[13], ast.Name) and CreateCalls[0].args[13].id == "AllClient"
    CoreSource = "\n".join(EffectText.splitlines()[CoreMethod.lineno - 1:CoreMethod.end_lineno])
    assert 'PostData = [entityId, Time, "black_hole:%s" % Id1]' in CoreSource
    assert "MappingCall(self._BlackHolePostLifecycle.__name__, PostData)" in CoreSource
    assert "self._BlackHolePostLifecycle(PostData)" in CoreSource

    LifecycleMethod = FindMethod(SkillEffectClass, "_BlackHolePostLifecycle")
    LifecycleSource = "\n".join(EffectText.splitlines()[LifecycleMethod.lineno - 1:LifecycleMethod.end_lineno])
    # Codex 2026-08-10: 后处理必须由独立令牌持有到 Time，不能再随 0.1 秒发射器销毁。
    assert 'entityId != playerId and not GetVaryingClient("OtherPlayerEffect", defaultValue=False)' in LifecycleSource
    assert 'SkillPostEffectSystem._SetPostState([entityId, "arris_black_hole", True, OwnerToken])' in LifecycleSource
    assert 'CreateTimer(Time, SkillPostEffectSystem._SetPostState, False,' in LifecycleSource
    assert '[entityId, "arris_black_hole", False, OwnerToken])' in LifecycleSource


def AssertDimensionalLightningContract():
    EffectText = SWS_EFFECT_PATH.read_text(encoding="utf-8-sig")
    SkillEffectClass = FindClass(ast.parse(EffectText), "SkillEffectSystem")
    MethodNode = FindMethod(SkillEffectClass, "DimensionalSeverLightningLocal")
    CreateCalls = [
        Node for Node in ast.walk(MethodNode)
        if isinstance(Node, ast.Call) and isinstance(Node.func, ast.Attribute) and Node.func.attr == "CreateSuperEffect"
    ]
    assert len(CreateCalls) == 2
    for CallNode in CreateCalls:
        assert isinstance(CallNode.args[0], ast.Name) and CallNode.args[0].id == "SharedRandom"
        assert isinstance(CallNode.args[13], ast.Constant) and CallNode.args[13].value is False
    MethodSource = "\n".join(EffectText.splitlines()[MethodNode.lineno - 1:MethodNode.end_lineno])
    # Codex 2026-08-03: 双层雷弧必须共享随机输入，并逐个沿既有客户端销毁入口清理。
    assert "SharedRandom = (Seed, FlickerVariant, time.time())" in MethodSource
    assert "for EffectId in (NormalEffectId, GlassOverlayEffectId):" in MethodSource
    assert "CreateTimer(Time+0.02, EngineClient.DestroySuperEffectClient, False, EffectId)" in MethodSource


def AssertMobRenderUsesSharedLocalPaths():
    RenderText = MOB_RENDER_PATH.read_text(encoding="utf-8")
    assert 'clientApi.ImportModule("FunctionScripts.KnifeLightRender")' in RenderText
    assert "self.trail_render_module.EntityAttackKnifeLightRenderer()" in RenderText
    assert '"_SetDirtParticleTimeStop", data' in RenderText
    assert '"DimensionalSeverLightningLocal", [entityId, effectTime]' in RenderText
    assert 'return self._call_sws_public_effect_local(componentName, methodName, args, {"AllClient": False})' in RenderText
    assert '("UndeadVortex", "UndeadSmoke", "DimensionalSeverRound", "DimensionalSeverGlass", "BlackHoleCore")' in RenderText


def Main():
    AssertStateEffectsMatch()
    AssertSwsLocalOnlySwitches()
    AssertBlackHolePostLifecycle()
    AssertDimensionalLightningContract()
    AssertMobRenderUsesSharedLocalPaths()
    print("katana Mob effect sync valid: undead/dimensional paths + black-hole post lifecycle/local bridge")


if __name__ == "__main__":
    Main()
