# coding=utf-8
"""SWS 特效质量分级、二级设置页与运行时门控的静态回归。"""

import ast
import hashlib
import math
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[4]
BEHAVIOR_ROOT = PROJECT_ROOT / "src" / "SwordSoul_NewERA_B"
SWS_ROOT = BEHAVIOR_ROOT / "SwordSoulFightScripts"
QUALITY_PATH = SWS_ROOT / "EffectSystem" / "Quality.py"
FIGHT_EFFECT_PATH = SWS_ROOT / "EffectSystem" / "Fight.py"
SCREEN_EFFECT_PATH = SWS_ROOT / "EffectSystem" / "Screen.py"
SETTING_DATA_PATH = SWS_ROOT / "UISystem" / "SettingData.py"
GENERAL_SCREEN_PATH = SWS_ROOT / "UISystem" / "GeneralScreen.py"
MAIN_SETTING_PATH = SWS_ROOT / "UISystem" / "MainSetting.py"
ENGINE_CLIENT_PATH = SWS_ROOT / "QingYunModLibs" / "QyEngine" / "EngineClient.py"
KATANA_STATE_PATH = SWS_ROOT / "FightSystem" / "UseKatanaState.py"
TRAIL_PATH = BEHAVIOR_ROOT / "FunctionScripts" / "KnifeLightRender.py"
HOCK_ROPE_PATH = SWS_ROOT / "FunctionSystem" / "HockRopeSystem.py"
CONTROL_PATH = SWS_ROOT / "UISystem" / "Control.py"
SPRINT_RADIAL_SHADER_PATH = PROJECT_ROOT / "src" / "SwordSoul_NewERA_R" / "shaders" / "post_process" / "glsl" / "arris_sprint_radial_blur_fragment.glsl"

QUALITY_SETTING_IDS = {
    "SkillEffectQuality",
    "SuperSkillEffectQuality",
    "CombatSceneEffectQuality",
    "PostProcessEffectQuality",
    "TrailQuality",
}
MIGRATED_EFFECT_IDS = QUALITY_SETTING_IDS | {
    "EffectQualityPreset",
    "TrailRender",
    "AttackEffect",
    "Bloom",
    "E_Bloom",
    "BloomPower",
    "BloomRange",
    "MotionBlur",
    "MotionBlurPower",
    "SprintTrail",
    "OtherPlayerEffect",
}


def ReadText(PathValue):
    return PathValue.read_text(encoding="utf-8-sig")


def ReadTree(PathValue):
    return ast.parse(ReadText(PathValue), filename=str(PathValue))


def FindClass(Tree, Name):
    return next(Node for Node in Tree.body if isinstance(Node, ast.ClassDef) and Node.name == Name)


def FindMethod(ClassNode, Name):
    return next(Node for Node in ClassNode.body if isinstance(Node, ast.FunctionDef) and Node.name == Name)


def CallsQualityAllows(MethodNode):
    return any(
        isinstance(Node, ast.Call)
        and isinstance(Node.func, ast.Attribute)
        and isinstance(Node.func.value, ast.Name)
        and Node.func.value.id == "Quality"
        and Node.func.attr == "Allows"
        for Node in ast.walk(MethodNode)
    )


def CallsMethod(MethodNode, MethodName):
    return any(
        isinstance(Node, ast.Call)
        and isinstance(Node.func, ast.Attribute)
        and Node.func.attr == MethodName
        for Node in ast.walk(MethodNode)
    )


def CallsQualityAllowsAtLevel(MethodNode, LevelName):
    for Node in ast.walk(MethodNode):
        if not (
            isinstance(Node, ast.Call)
            and isinstance(Node.func, ast.Attribute)
            and isinstance(Node.func.value, ast.Name)
            and Node.func.value.id == "Quality"
            and Node.func.attr == "Allows"
            and len(Node.args) >= 2
        ):
            continue
        RequiredNode = Node.args[1]
        if (
            isinstance(RequiredNode, ast.Attribute)
            and isinstance(RequiredNode.value, ast.Name)
            and RequiredNode.value.id == "Quality"
            and RequiredNode.attr == LevelName
        ):
            return True
    return False


def GetCreateSuperEffectRequiredQuality(MethodNode):
    CallNode = next(
        Node for Node in ast.walk(MethodNode)
        if isinstance(Node, ast.Call)
        and isinstance(Node.func, ast.Attribute)
        and Node.func.attr == "CreateSuperEffect"
    )
    KeywordMap = dict((Keyword.arg, Keyword.value) for Keyword in CallNode.keywords)
    return KeywordMap.get("RequiredQuality", CallNode.args[15] if len(CallNode.args) > 15 else None)


def IsQualityLevel(Node, LevelName):
    return (
        isinstance(Node, ast.Attribute)
        and isinstance(Node.value, ast.Name)
        and Node.value.id == "Quality"
        and Node.attr == LevelName
    )


def CollectConfigIds(ClassNode):
    Result = set()
    for Node in ast.walk(ClassNode):
        if isinstance(Node, ast.Dict):
            for Key, Value in zip(Node.keys, Node.values):
                if isinstance(Key, ast.Constant) and Key.value == "id" and isinstance(Value, ast.Constant):
                    Result.add(Value.value)
        elif isinstance(Node, ast.Call) and isinstance(Node.func, ast.Attribute) and Node.func.attr == "_QualityConfig":
            if Node.args and isinstance(Node.args[0], ast.Constant):
                Result.add(Node.args[0].value)
    return Result


def LoadConstantAssignment(Tree, Name, Namespace):
    Assignment = next(
        Node for Node in Tree.body
        if isinstance(Node, ast.Assign)
        and any(isinstance(Target, ast.Name) and Target.id == Name for Target in Node.targets)
    )
    Module = ast.Module(body=[Assignment], type_ignores=[])
    ast.fix_missing_locations(Module)
    exec(compile(Module, str(QUALITY_PATH), "exec"), Namespace)
    return Namespace[Name]


def AssertPresetContract():
    Tree = ReadTree(QUALITY_PATH)
    Namespace = {"QUALITY_LOW": 0, "QUALITY_MEDIUM": 1, "QUALITY_HIGH": 2}
    CategoryMap = LoadConstantAssignment(Tree, "CATEGORY_SETTING_MAP", Namespace)
    Presets = LoadConstantAssignment(Tree, "EFFECT_QUALITY_PRESETS", Namespace)
    TrailProfiles = LoadConstantAssignment(Tree, "TRAIL_QUALITY_PROFILE", Namespace)
    assert set(CategoryMap.values()) == QUALITY_SETTING_IDS
    assert set(Presets) == {0, 1, 2, 3}
    for Preset, Profile in Presets.items():
        assert QUALITY_SETTING_IDS <= set(Profile), Preset
        assert Profile["TrailRender"] is True, Preset
        assert Profile["AttackEffect"] is True, Preset
        assert Profile["SneakingTips"] is True, Preset
    assert [TrailProfiles[Index]["sample_fps"] for Index in (0, 1, 2)] == [30.0, 60.0, 120.0]
    assert TrailProfiles[0]["particle_enabled"] is False
    return len(Presets), len(CategoryMap)


def AssertUiMigration():
    Tree = ReadTree(GENERAL_SCREEN_PATH)
    VisualIds = CollectConfigIds(FindClass(Tree, "VisualScreen"))
    EffectIds = CollectConfigIds(FindClass(Tree, "EffectSettingScreen"))
    assert "EffectSettingsEntry" in VisualIds
    # Codex 2026-08-06: 蓄力提示属于视觉辅助，保留在视觉设置而非特效质量细项页。
    assert "SneakingTips" in VisualIds
    assert "SneakingTips" not in EffectIds
    assert not (MIGRATED_EFFECT_IDS & VisualIds), sorted(MIGRATED_EFFECT_IDS & VisualIds)
    assert MIGRATED_EFFECT_IDS <= EffectIds, sorted(MIGRATED_EFFECT_IDS - EffectIds)
    MainText = ReadText(MAIN_SETTING_PATH)
    assert "self.EffectSettingScreen = GeneralScreen.EffectSettingScreen()" in MainText
    assert "def ShowEffectSettingScreen(self):" in MainText
    return len(VisualIds), len(EffectIds)


def AssertPersistenceAndOptimizer():
    Text = ReadText(SETTING_DATA_PATH)
    for SettingId in QUALITY_SETTING_IDS | {"EffectQualityPreset"}:
        assert 'self.SetLocalConfig("%s", True)' % SettingId in Text, SettingId
        assert "def on%s(self, Value):" % SettingId in Text, SettingId
    assert "def ApplyEffectQualityPreset(self, Preset):" in Text
    assert "def MarkEffectQualityCustom(self):" in Text
    assert ".GetFps()" in Text
    assert "StableFps = Samples[int((len(Samples) - 1) * 0.25)]" in Text
    assert "if len(Samples) < 4:" in Text
    Tree = ReadTree(SETTING_DATA_PATH)
    SettingClass = FindClass(Tree, "ChooseSettingSystem")
    OtherPlayerMethod = next(
        Node for Node in SettingClass.body
        if isinstance(Node, ast.FunctionDef) and Node.name == "onOtherPlayerEffect"
    )
    assert any(
        isinstance(Node, ast.Call)
        and isinstance(Node.func, ast.Attribute)
        and Node.func.attr == "RefreshQuality"
        for Node in ast.walk(OtherPlayerMethod)
    )
    RefreshedComponents = set()
    for Node in ast.walk(OtherPlayerMethod):
        if (
            isinstance(Node, ast.Call)
            and isinstance(Node.func, ast.Name)
            and Node.func.id == "GetComponent"
            and Node.args
            and isinstance(Node.args[0], ast.Constant)
        ):
            RefreshedComponents.add(Node.args[0].value)
    assert {"AttackEffectSystem", "SneakingEffectSystem", "SkillPostEffectSystem"} <= RefreshedComponents


def AssertSuperEffectMetadata():
    Tree = ReadTree(FIGHT_EFFECT_PATH)
    Calls = []
    for Node in ast.walk(Tree):
        if not isinstance(Node, ast.Call) or not isinstance(Node.func, ast.Attribute):
            continue
        if Node.func.attr != "CreateSuperEffect":
            continue
        KeywordMap = dict((Keyword.arg, Keyword.value) for Keyword in Node.keywords)
        CategoryNode = KeywordMap.get("QualityCategory")
        RequiredNode = KeywordMap.get("RequiredQuality")
        EffectKeyNode = KeywordMap.get("EffectKey")
        if CategoryNode is None and len(Node.args) > 14:
            CategoryNode = Node.args[14]
        if RequiredNode is None and len(Node.args) > 15:
            RequiredNode = Node.args[15]
        if EffectKeyNode is None and len(Node.args) > 16:
            EffectKeyNode = Node.args[16]
        Calls.append((Node.lineno, CategoryNode, RequiredNode, EffectKeyNode))
    assert Calls
    Missing = [Line for Line, Category, Required, EffectKey in Calls if None in (Category, Required, EffectKey)]
    assert not Missing, Missing
    InvalidCategories = []
    for Line, Category, Required, EffectKey in Calls:
        try:
            CategoryValue = ast.literal_eval(Category)
        except (ValueError, TypeError):
            InvalidCategories.append(Line)
            continue
        if CategoryValue not in ("skill", "ultimate", "combat_scene"):
            InvalidCategories.append(Line)
    assert not InvalidCategories, InvalidCategories
    EngineText = ReadText(ENGINE_CLIENT_PATH)
    assert "QualityCategory=\"\"" in EngineText
    assert "Quality.ShouldCreateEffect(" in EngineText
    assert "Quality.GetEmissionScale(" in EngineText
    return len(Calls)


def AssertRuntimeQualityGuards():
    ScreenText = ReadText(SCREEN_EFFECT_PATH)
    TrailText = ReadText(TRAIL_PATH)
    assert "Quality.AllowsPost(PostName, SourceId)" in ScreenText
    assert "def RefreshQuality(self):" in ScreenText
    assert "self.UpdatePostState(Entity, PostName, False, OwnerToken)" in ScreenText
    assert "def SetEffectQuality(trailQuality, postQuality):" in TrailText
    assert "_TRAIL_SAMPLE_FPS = (30.0, 60.0, 120.0)" in TrailText
    assert "_TRAIL_PARTICLE_FRAME_CAP = (0, 24, 64)" in TrailText
    assert "_refreshTrailPostStates()" in TrailText
    FightTree = ReadTree(FIGHT_EFFECT_PATH)
    AttackEffectClass = FindClass(FightTree, "AttackEffectSystem")
    # Codex 2026-08-06: 刮擦、擦地和收刀火花是装饰层，最低战斗交互档必须关闭。
    for MethodName in ("onHit", "onDoomHit", "HitGround", "Shodao"):
        MethodText = ast.get_source_segment(ReadText(FIGHT_EFFECT_PATH), FindMethod(AttackEffectClass, MethodName))
        assert "Quality.QUALITY_MEDIUM" in MethodText, MethodName
    assert '"combat_scene", Quality.QUALITY_MEDIUM, "hit_sparks"' in ReadText(FIGHT_EFFECT_PATH)
    assert 'RequiredQuality=Quality.QUALITY_LOW, EffectKey="doom_hit_sparks"' not in ReadText(FIGHT_EFFECT_PATH)
    assert CallsQualityAllows(FindMethod(FindClass(FightTree, "StickSlashExpress"), "posExpression"))
    SneakingClass = FindClass(FightTree, "SneakingEffectSystem")
    assert CallsQualityAllows(FindMethod(SneakingClass, "_SneakingTipsEffect"))
    assert CallsQualityAllows(FindMethod(SneakingClass, "RefreshQuality"))
    AttackRefresh = FindMethod(AttackEffectClass, "RefreshQuality")
    assert CallsMethod(AttackRefresh, "_AllowsDirtSmoke")
    assert CallsQualityAllows(FindMethod(AttackEffectClass, "_AllowsDirtSmoke"))
    HockTree = ReadTree(HOCK_ROPE_PATH)
    assert CallsQualityAllows(FindMethod(FindClass(HockTree, "HockRopeSystem"), "HockTarget"))
    SprintShaderText = ReadText(SPRINT_RADIAL_SHADER_PATH)
    # Codex 2026-08-10: 极速攻击保留向心压缩，疾跑负权重必须硬切原始UV且保留径向采样。
    for ShaderToken in (
        "view_center_y", "speed_stretch", "edge_extent", "view_ratio",
        "border_radius", "inward_strength", "inward_scale", "stretched_uv"
    ):
        assert ShaderToken in SprintShaderText, ShaderToken
    for RemovedToken in ("speed_view_scale", "edge_ratio", "fov_exponent", "stretched_ratio"):
        assert RemovedToken not in SprintShaderText, RemovedToken
    assert "float inward_strength = 0.65 * speed_stretch" in SprintShaderText
    assert "float inward_scale = 1.0 + inward_strength * (1.0 - border_radius)" in SprintShaderText
    assert "uniform vec4 EXTRA_VECTOR2" in SprintShaderText
    assert "float view_center_y = clamp(EXTRA_VECTOR2.x, 0.30, 0.74)" in SprintShaderText
    assert "vec2 center = vec2(0.5, view_center_y)" in SprintShaderText
    assert "vec2 center = vec2(0.5, 0.52)" not in SprintShaderText
    assert "float encoded_radial_weight = EXTRA_VECTOR1.w" in SprintShaderText
    assert "vec2 stretched_uv = uv" in SprintShaderText
    assert "if (encoded_radial_weight >= 0.0)" in SprintShaderText
    assert "clamp(abs(encoded_radial_weight), 0.0, 1.0)" in SprintShaderText
    assert "stretch_power" not in SprintShaderText
    assert "EXTRA_VECTOR2.y" not in SprintShaderText
    assert "center + view_ratio * inward_scale * edge_extent" in SprintShaderText
    assert "texture(TEXTURE_0, stretched_uv)" in SprintShaderText
    for SpeedRate in (0.0, 0.25, 0.5, 0.75, 1.0):
        InwardStrength = 0.65 * SpeedRate
        MappedRadius = [
            Radius + InwardStrength * Radius * (1.0 - Radius)
            for Radius in (Index / 100.0 for Index in range(101))
        ]
        assert MappedRadius[0] == 0.0
        assert MappedRadius[-1] == 1.0
        assert all(MappedRadius[Index] >= MappedRadius[Index - 1] for Index in range(1, len(MappedRadius)))
        assert all(0.0 <= Radius <= 1.0 for Radius in MappedRadius)
    FullMappedRadius = [
        Radius + 0.65 * Radius * (1.0 - Radius)
        for Radius in (Index / 100.0 for Index in range(101))
    ]
    FullDisplacement = [
        FullMappedRadius[Index] - Index / 100.0
        for Index in range(101)
    ]
    assert abs(FullMappedRadius[50] - 0.6625) < 0.000000001
    assert FullDisplacement.index(max(FullDisplacement)) == 50
    assert FullDisplacement[0] == 0.0
    assert FullDisplacement[-1] == 0.0
    def MapViewCoordinate(Coordinate, SpeedRate, CenterY=0.52):
        ViewCenter = (0.5, CenterY)
        FromCenter = tuple(Coordinate[Index] - ViewCenter[Index] for Index in range(2))
        EdgeExtent = tuple(
            (1.0 - ViewCenter[Index]) if FromCenter[Index] >= 0.0 else ViewCenter[Index]
            for Index in range(2)
        )
        ViewRatio = tuple(FromCenter[Index] / EdgeExtent[Index] for Index in range(2))
        BorderRadius = max(abs(ViewRatio[0]), abs(ViewRatio[1]))
        InwardScale = 1.0 + 0.65 * SpeedRate * (1.0 - BorderRadius)
        return tuple(
            ViewCenter[Index] + ViewRatio[Index] * InwardScale * EdgeExtent[Index]
            for Index in range(2)
        )

    for CenterY in (0.30, 0.52, 0.74):
        for EdgePoint in ((0.0, 0.2), (1.0, 0.8), (0.3, 0.0), (0.7, 1.0)):
            MappedEdge = MapViewCoordinate(EdgePoint, 1.0, CenterY)
            assert all(abs(MappedEdge[Index] - EdgePoint[Index]) < 0.000000001 for Index in range(2))
        assert MapViewCoordinate((0.5, CenterY), 1.0, CenterY) == (0.5, CenterY)
    assert MapViewCoordinate((0.75, 0.52), 1.0)[0] > 0.75
    assert MapViewCoordinate((0.25, 0.52), 1.0)[0] < 0.25

    def PitchToViewCenterY(Pitch, CameraFov=62.8, PitchScale=0.20):
        CameraPitch = min(89.0, max(-89.0, Pitch))
        CameraFov = min(110.0, max(30.0, CameraFov))
        ProjectionScale = max(math.tan(math.radians(CameraFov * 0.5)), 0.001)
        ProjectionOffset = PitchScale * math.tan(math.radians(CameraPitch)) / ProjectionScale
        return min(0.74, max(0.30, 0.52 + ProjectionOffset))

    assert abs(PitchToViewCenterY(-90.0) - 0.30) < 0.000000001
    assert abs(PitchToViewCenterY(0.0) - 0.52) < 0.000000001
    assert abs(PitchToViewCenterY(90.0) - 0.74) < 0.000000001
    # Codex 2026-08-10: 小角度仍反向偏移，但幅度必须收敛到准星附近。
    assert 0.47 < PitchToViewCenterY(-7.0) < 0.49
    assert 0.55 < PitchToViewCenterY(7.0) < 0.57
    CenterFollowResults = []
    for FrameRate in (30, 60, 120):
        CurrentCenterY = 0.52
        TargetCenterY = 0.30
        DeltaTime = 1.0 / FrameRate
        for Index in range(int(0.4 * FrameRate)):
            FollowRatio = 1.0 - 2.0 ** (-DeltaTime / 0.04)
            CurrentCenterY += (TargetCenterY - CurrentCenterY) * FollowRatio
            assert 0.30 <= CurrentCenterY <= 0.52
        CenterFollowResults.append(CurrentCenterY)
    assert max(CenterFollowResults) - min(CenterFollowResults) < 0.000000001

    # Codex 2026-08-07: 径向模糊中心允许动态输入，方向、噪声公式和四层等权采样仍必须锁定。
    RadialStart = SprintShaderText.index("    vec2 motion_dir = EXTRA_VECTOR1.yz;")
    RadialEnd = SprintShaderText.index("    gl_FragColor =", RadialStart)
    RadialBlock = SprintShaderText[RadialStart:RadialEnd]
    assert hashlib.sha256(RadialBlock.encode("utf-8")).hexdigest() == "f048465f7ecc0d8c7279ff0285a3c5f7c52279d9129aa268396c5179e5f7fdcc"
    # Codex 2026-08-06: H键热更入口必须持续覆盖当前修改的冲刺后处理shader。
    assert 'ReloadOneShader("arris_sprint_radial_blur_fragment")' in ReadText(CONTROL_PATH)
    ScreenTree = ReadTree(SCREEN_EFFECT_PATH)
    BasePostClass = FindClass(ScreenTree, "BasePostEffectSystem")
    SprintTickMethod = FindMethod(BasePostClass, "OnSprintRadialBlur")
    SprintTickText = ast.get_source_segment(ReadText(SCREEN_EFFECT_PATH), SprintTickMethod)
    SprintTickDecorators = [
        ast.get_source_segment(ReadText(SCREEN_EFFECT_PATH), Decorator)
        for Decorator in SprintTickMethod.decorator_list
    ]
    SprintDirectionEncodeText = ast.get_source_segment(
        ReadText(SCREEN_EFFECT_PATH), FindMethod(BasePostClass, "EncodeSprintRadialBlurDirection")
    )
    # Codex 2026-08-10: 疾跑必须通过既有direction参数负号进入Shader硬隔离分支。
    assert 'EffectMode != "sprint"' in SprintDirectionEncodeText
    assert "-max(Direction[2], 0.001)" in SprintDirectionEncodeText
    SprintCenterTargetText = ast.get_source_segment(
        ReadText(SCREEN_EFFECT_PATH), FindMethod(BasePostClass, "GetSprintRadialBlurTargetViewCenterY")
    )
    SprintCenterUpdateText = ast.get_source_segment(
        ReadText(SCREEN_EFFECT_PATH), FindMethod(BasePostClass, "UpdateSprintRadialBlurViewCenterY")
    )
    # Codex 2026-08-06: 强度必须快进慢退地连续跟随速度，不能冻结峰值后按固定曲线骤降。
    assert "SprintRadialBlurPowerVelocity" in SprintTickText
    # Codex 2026-08-08: 视野拉伸必须逐渲染帧更新，禁止退回固定30Tick事件。
    assert 'BaseComponent.ComponentListenEvent("GameRenderTickEvent")' in SprintTickDecorators
    assert all("OnScriptTickClient" not in Decorator for Decorator in SprintTickDecorators)
    assert [Arg.arg for Arg in SprintTickMethod.args.args] == ["self"]
    assert SprintTickMethod.args.vararg is not None
    assert SprintTickMethod.args.vararg.arg == "args"
    assert not SprintTickMethod.args.defaults
    assert "SprintRadialBlurFadeInTime if TargetPower >= self.SprintRadialBlurPower else self.SprintRadialBlurFadeOutTime" in SprintTickText
    assert "0.48 * SmoothDelta * SmoothDelta" in SprintTickText
    assert "SprintRadialBlurReleaseStartPower" not in SprintTickText
    assert "ReleaseCurve" not in SprintTickText
    assert '"direction", self.SprintRadialBlurDirection' in SprintTickText
    assert '"view_center_y", self.SprintRadialBlurViewCenterY' in SprintTickText
    assert "ClientApi.Player.Camera.GetCameraRotation()" in SprintCenterTargetText
    assert "ClientApi.Player.Camera.GetFov()" in SprintCenterTargetText
    assert "math.tan(math.radians(CameraFov * 0.5))" in SprintCenterTargetText
    assert "math.tan(math.radians(CameraPitch))" in SprintCenterTargetText
    assert "self.SprintRadialBlurViewCenterBaseY + ProjectionOffset" in SprintCenterTargetText
    assert "self.SprintRadialBlurViewCenterPitchScale * math.tan" in SprintCenterTargetText
    assert "2.0 ** (-DeltaTime / max(self.SprintRadialBlurViewCenterHalfLife, 0.001))" in SprintCenterUpdateText
    assert "0.12 / self.SprintRadialBlurFadeOutTime" not in SprintTickText
    ScreenText = ReadText(SCREEN_EFFECT_PATH)
    assert '{"name": "view_center_y", "value": self.SprintRadialBlurViewCenterBaseY, "range": [0.30, 0.74]}' in ScreenText
    assert "self.SprintRadialBlurFadeInTime = 0.055" in ScreenText
    # Codex 2026-08-08: 锁定冲刺视野约快50%的回正阻尼，防止后续调参退回慢恢复。
    assert "self.SprintRadialBlurFadeOutTime = 0.125" in ScreenText
    # 临界阻尼的减弱首帧只产生很小位移，随后连续加速再柔和收尾。
    Power = 1.0
    Velocity = 0.0
    ReleaseValues = [Power]
    for Index in range(120):
        DeltaTime = 1.0 / 60.0
        Omega = 2.0 / 0.19
        SmoothDelta = Omega * DeltaTime
        SmoothExp = 1.0 / (1.0 + SmoothDelta + 0.48 * SmoothDelta ** 2 + 0.235 * SmoothDelta ** 3)
        PowerDelta = Power
        VelocityStep = (Velocity + Omega * PowerDelta) * DeltaTime
        Velocity = (Velocity - Omega * VelocityStep) * SmoothExp
        Power = (PowerDelta + VelocityStep) * SmoothExp
        ReleaseValues.append(Power)
    assert ReleaseValues[1] > 0.98
    assert all(ReleaseValues[Index] <= ReleaseValues[Index - 1] for Index in range(1, len(ReleaseValues)))
    assert ReleaseValues[-1] < 0.001


def AssertDirtSmokeToggleContract():
    SettingText = ReadText(SETTING_DATA_PATH)
    GeneralText = ReadText(GENERAL_SCREEN_PATH)
    QualityText = ReadText(QUALITY_PATH)
    FightTree = ReadTree(FIGHT_EFFECT_PATH)
    AttackEffectClass = FindClass(FightTree, "AttackEffectSystem")

    assert "self.DirtSmokeEffect = True" in SettingText
    assert 'self.SetLocalConfig("DirtSmokeEffect", True)' in SettingText
    assert "def onDirtSmokeEffect(self, State):" in SettingText
    assert '"id": "DirtSmokeEffect"' in GeneralText
    assert '"label": "尘土飞扬"' in GeneralText
    # 独立开关不属于快速画质预设，切换预设不得把用户手动选择覆盖掉。
    assert "DirtSmokeEffect" not in QualityText

    AllowsMethod = FindMethod(AttackEffectClass, "_AllowsDirtSmoke")
    AllowsText = ast.get_source_segment(ReadText(FIGHT_EFFECT_PATH), AllowsMethod)
    assert 'GetComponent("ChooseSettingSystem")' in AllowsText
    assert 'getattr(SettingSystem, "DirtSmokeEffect", True)' in AllowsText
    assert CallsQualityAllows(AllowsMethod)
    for MethodName in (
        "_DirtSmokeEffect",
        "_CreateSingleSmokeEffect",
        "_TickSprintDirtSmokeEmission",
        "_CreateDirtSmokeTrailEffect",
        "RefreshQuality",
    ):
        assert CallsMethod(FindMethod(AttackEffectClass, MethodName), "_AllowsDirtSmoke"), MethodName

    SettingTree = ReadTree(SETTING_DATA_PATH)
    SettingClass = FindClass(SettingTree, "ChooseSettingSystem")
    assert CallsMethod(FindMethod(SettingClass, "onDirtSmokeEffect"), "RefreshQuality")


def AssertKnifeTrailBloomQualityContract():
    # Codex 2026-08-10: 最低画面档必须同时保留刀光专属 Bloom 与破空气流。
    QualityTree = ReadTree(QUALITY_PATH)
    Namespace = {"QUALITY_LOW": 0, "QUALITY_MEDIUM": 1, "QUALITY_HIGH": 2}
    PostQuality = LoadConstantAssignment(QualityTree, "POST_PROCESS_REQUIRED_QUALITY", Namespace)
    assert PostQuality["arris_bloom_trail"] == 0
    assert PostQuality["arris_airflow"] == 0

    TrailText = ReadText(TRAIL_PATH)
    assert 'return effect in ("bloom", "airflow")' in TrailText
    assert '"arris_bloom_trail", "arris_bloom_trail" in ActivePosts' in TrailText
    assert '"arris_airflow" in ActivePosts and _trailPostEnabled("airflow")' in TrailText
    assert 'for PostName in ("arris_bloom_trail", "arris_airflow")' not in TrailText

    ScreenTree = ReadTree(SCREEN_EFFECT_PATH)
    BasePostClass = FindClass(ScreenTree, "BasePostEffectSystem")
    RefreshText = ast.get_source_segment(
        ReadText(SCREEN_EFFECT_PATH), FindMethod(BasePostClass, "RefreshQuality")
    )
    assert 'self.InitTrailBloom()' in RefreshText
    assert 'self.InitAirflow()' in RefreshText
    assert 'SetEnableByName("arris_airflow", False)' not in RefreshText
    assert '"arris_bloom_trail"' not in RefreshText

    SkillPostClass = FindClass(ScreenTree, "SkillPostEffectSystem")
    InitPostText = ast.get_source_segment(
        ReadText(SCREEN_EFFECT_PATH), FindMethod(SkillPostClass, "InitPost")
    )
    assert 'BasePostEffectSystemObj.InitTrailBloom()' in InitPostText
    assert 'BasePostEffectSystemObj.InitAirflow()' in InitPostText

    TrailTree = ReadTree(TRAIL_PATH)
    HelperNames = {
        "SetEffectQuality", "_trailPostEnabled", "_getTrailPostName", "_refreshTrailPostStates"
    }
    HelperNodes = [
        Node for Node in TrailTree.body
        if isinstance(Node, ast.FunctionDef) and Node.name in HelperNames
    ]
    assert set(Node.name for Node in HelperNodes) == HelperNames

    class FakePostProcess(object):
        def __init__(self):
            self.StateMap = {}

        def SetEnableByName(self, PostName, State):
            self.StateMap[PostName] = bool(State)

    class FakeTrailEffect(object):
        effectMap = {"none": 0, "bloom": 1, "airflow": 2}
        effectPostMap = {
            "bloom": "arris_bloom_trail",
            "airflow": "arris_airflow",
        }

        def __init__(self, Effect):
            self.binderArgs = {"effect": Effect}

    FakePost = FakePostProcess()
    Namespace = {
        "PostStateMap": set(),
        "PostProcessComp": FakePost,
        "_TRAIL_QUALITY_LEVEL": [2],
        "_TRAIL_POST_QUALITY_LEVEL": [2],
    }
    HelperModule = ast.Module(body=HelperNodes, type_ignores=[])
    ast.fix_missing_locations(HelperModule)
    exec(compile(HelperModule, str(TRAIL_PATH), "exec"), Namespace)

    # Codex 2026-08-10: 动态降至最低档后，仍只按活跃刀光类型切换泛光与气流。
    Namespace["PostStateMap"].add(FakeTrailEffect(1))
    Namespace["SetEffectQuality"](0, 0)
    assert FakePost.StateMap["arris_bloom_trail"] is True
    assert FakePost.StateMap["arris_airflow"] is False
    Namespace["PostStateMap"].clear()
    Namespace["PostStateMap"].add(FakeTrailEffect(2))
    Namespace["SetEffectQuality"](0, 0)
    assert FakePost.StateMap["arris_bloom_trail"] is False
    assert FakePost.StateMap["arris_airflow"] is True
    Namespace["SetEffectQuality"](0, 1)
    assert FakePost.StateMap["arris_airflow"] is True


def AssertDimensionalSeverQualityContract():
    # Codex 2026-08-06: 锁定次元斩“核心常驻、后处理与密集装饰可裁剪”的独立分层。
    QualityTree = ReadTree(QUALITY_PATH)
    Namespace = {"QUALITY_LOW": 0, "QUALITY_MEDIUM": 1, "QUALITY_HIGH": 2}
    PostQuality = LoadConstantAssignment(QualityTree, "POST_PROCESS_REQUIRED_QUALITY", Namespace)
    assert PostQuality["arris_dimensional_sever"] == 0

    FightTree = ReadTree(FIGHT_EFFECT_PATH)
    SkillClass = FindClass(FightTree, "SkillEffectSystem")
    assert IsQualityLevel(
        GetCreateSuperEffectRequiredQuality(FindMethod(SkillClass, "DimensionalSeverRound")),
        "QUALITY_MEDIUM"
    )
    assert IsQualityLevel(
        GetCreateSuperEffectRequiredQuality(FindMethod(SkillClass, "DimensionalSeverGlass")),
        "QUALITY_LOW"
    )
    LightningMethod = FindMethod(SkillClass, "DimensionalSeverLightningLocal")
    # Codex 2026-08-06: 白色骨骼雷网的接收端与普通 Pass 均只允许高终结技档位。
    assert not CallsQualityAllowsAtLevel(LightningMethod, "QUALITY_LOW")
    assert not CallsQualityAllowsAtLevel(LightningMethod, "QUALITY_MEDIUM")
    assert CallsQualityAllowsAtLevel(
        LightningMethod, "QUALITY_HIGH"
    )
    assert IsQualityLevel(
        GetCreateSuperEffectRequiredQuality(LightningMethod), "QUALITY_HIGH"
    )
    assert CallsQualityAllowsAtLevel(
        FindMethod(SkillClass, "_DimensionalSeverSlash"), "QUALITY_MEDIUM"
    )

    KatanaTree = ReadTree(KATANA_STATE_PATH)
    ModuleMethods = dict(
        (Node.name, Node) for Node in KatanaTree.body if isinstance(Node, ast.FunctionDef)
    )
    for MethodName in ("_DistortPower", "_ShootPower", "__DistortPower", "__ShootPower"):
        assert CallsQualityAllowsAtLevel(ModuleMethods[MethodName], "QUALITY_MEDIUM"), MethodName
    DimensionalClass = FindClass(KatanaTree, "DimensionalSever")
    OnStart = FindMethod(DimensionalClass, "onStart")
    RoundParticleCalls = []
    for Node in ast.walk(OnStart):
        if not (
            isinstance(Node, ast.Call)
            and isinstance(Node.func, ast.Attribute)
            and Node.func.attr == "playParticle"
            and Node.args
            and isinstance(Node.args[0], ast.Constant)
            and Node.args[0].value == "arris:dimensional_sever_round"
        ):
            continue
        KeywordMap = dict((Keyword.arg, Keyword.value) for Keyword in Node.keywords)
        RoundParticleCalls.append(KeywordMap.get("RequiredQuality"))
    assert len(RoundParticleCalls) == 1
    assert IsQualityLevel(RoundParticleCalls[0], "QUALITY_MEDIUM")


def AssertBlackHoleQualityContract():
    # Codex 2026-08-10: 锁定量子坍缩后处理为低档核心，外围粒子仍从中档启用。
    QualityTree = ReadTree(QUALITY_PATH)
    Namespace = {"QUALITY_LOW": 0, "QUALITY_MEDIUM": 1, "QUALITY_HIGH": 2}
    PostQuality = LoadConstantAssignment(QualityTree, "POST_PROCESS_REQUIRED_QUALITY", Namespace)
    assert PostQuality["arris_black_hole"] == 0

    FightTree = ReadTree(FIGHT_EFFECT_PATH)
    SkillClass = FindClass(FightTree, "SkillEffectSystem")
    assert IsQualityLevel(
        GetCreateSuperEffectRequiredQuality(FindMethod(SkillClass, "BlackHoleCore")),
        "QUALITY_LOW"
    )
    BlackHolePartText = ast.get_source_segment(
        ReadText(FIGHT_EFFECT_PATH), FindMethod(SkillClass, "BlackHolePart")
    )
    assert "RequiredQuality=Quality.QUALITY_MEDIUM" in BlackHolePartText


def main():
    PresetCount, CategoryCount = AssertPresetContract()
    VisualCount, EffectCount = AssertUiMigration()
    AssertPersistenceAndOptimizer()
    SuperEffectCount = AssertSuperEffectMetadata()
    AssertRuntimeQualityGuards()
    AssertDirtSmokeToggleContract()
    AssertKnifeTrailBloomQualityContract()
    AssertDimensionalSeverQualityContract()
    AssertBlackHoleQualityContract()
    print(
        "effect quality system test passed: presets=%d categories=%d visual_items=%d "
        "effect_items=%d super_effect_calls=%d"
        % (PresetCount, CategoryCount, VisualCount, EffectCount, SuperEffectCount)
    )


if __name__ == "__main__":
    main()
