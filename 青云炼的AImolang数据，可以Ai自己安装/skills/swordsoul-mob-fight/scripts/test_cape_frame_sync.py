# coding=utf-8
"""流光披风单次连续时间推进与防抖静态回归。"""

import ast
import json
import math
import re
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[4]
TRAIL_PATH = PROJECT_ROOT / "src" / "SwordSoul_NewERA_B" / "FunctionScripts" / "KnifeLightRender.py"
SHADER_PATHS = {
    "arris_knife_light_normal": PROJECT_ROOT / "src" / "SwordSoul_NewERA_R" / "shaders" / "knife_light" / "glsl" / "arris_knife_light_fragment.glsl",
    "arris_knife_light_mark": PROJECT_ROOT / "src" / "SwordSoul_NewERA_R" / "shaders" / "knife_light" / "glsl" / "arris_knife_light_mark_fragment.glsl",
    "arris_trail_undead_wave": PROJECT_ROOT / "src" / "SwordSoul_NewERA_R" / "shaders" / "skill" / "undead_slash" / "glsl" / "arris_trail_undead_wave_fragment.glsl",
    "arris_trail_undead_smoke": PROJECT_ROOT / "src" / "SwordSoul_NewERA_R" / "shaders" / "skill" / "undead_slash" / "glsl" / "arris_trail_undead_smoke_fragment.glsl",
}
GEO_PATHS = (
    PROJECT_ROOT / "src" / "SwordSoul_NewERA_R" / "models" / "entity" / "player" / "PlayerLocator.geo.json",
    PROJECT_ROOT / "src" / "SwordSoul_NewERA_R" / "models" / "entity" / "ysm" / "PlayerLocator.geo.json",
    PROJECT_ROOT / "src" / "SwordSoul_NewERA_R" / "models" / "entity" / "player" / "PlayerBetter.geo.json",
)


def ReadSource():
    return TRAIL_PATH.read_text(encoding="utf-8")


def FindClass(Tree, Name):
    return next(Node for Node in Tree.body if isinstance(Node, ast.ClassDef) and Node.name == Name)


def FindMethod(ClassNode, Name):
    return next(Node for Node in ClassNode.body if isinstance(Node, ast.FunctionDef) and Node.name == Name)


def FindLocatorMaps(Value):
    LocatorMaps = []
    if isinstance(Value, dict):
        if isinstance(Value.get("locators"), dict):
            LocatorMaps.append(Value["locators"])
        for ChildValue in Value.values():
            LocatorMaps.extend(FindLocatorMaps(ChildValue))
    elif isinstance(Value, list):
        for ChildValue in Value:
            LocatorMaps.extend(FindLocatorMaps(ChildValue))
    return LocatorMaps


def LoadSimulationNamespace(Tree):
    ConstantNames = {
        "_TRAIL_SAMPLE_FPS",
        "_CAPE_MAX_FRAME_DELTA",
    }
    FunctionNames = {
        "radians",
        "rotateZXY",
        "getLength",
        "normalize",
        "_vecRemove",
        "_vecMultiply",
        "_vecCross",
        "_vecNeg",
        "_vecDot",
        "_toVec3",
        "_rotateVectorInBasis",
        "_getCapeFrameDelta",
    }
    Body = []
    for Node in Tree.body:
        if isinstance(Node, ast.Assign) and any(
            isinstance(Target, ast.Name) and Target.id in ConstantNames
            for Target in Node.targets
        ):
            Body.append(Node)
        elif isinstance(Node, ast.FunctionDef) and Node.name in FunctionNames:
            Body.append(Node)
    Namespace = {"math": math}
    Module = ast.Module(body=Body, type_ignores=[])
    ast.fix_missing_locations(Module)
    exec(compile(Module, str(TRAIL_PATH), "exec"), Namespace)
    return Namespace


def RunSchedule(GetFrameDelta, Deltas):
    return sum(GetFrameDelta(Delta) for Delta in Deltas)


def main():
    Source = ReadSource()
    Tree = ast.parse(Source, filename=str(TRAIL_PATH))
    Namespace = LoadSimulationNamespace(Tree)
    GetFrameDelta = Namespace["_getCapeFrameDelta"]
    RotateVectorInBasis = Namespace["_rotateVectorInBasis"]

    # Codex 2026-08-06: 三档稳定帧率下，一秒内的连续推进时间必须完全一致。
    for FrameRate in (30, 60, 120):
        SimulatedTime = RunSchedule(
            GetFrameDelta,
            [1.0 / FrameRate for Index in range(FrameRate)]
        )
        assert abs(SimulatedTime - 1.0) < 0.000000001, (FrameRate, SimulatedTime)

    # Codex 2026-08-06: 交替快慢帧仍按真实时间推进，异常长帧只能单次推进到 30FPS 上限。
    SimulatedTime = RunSchedule(
        GetFrameDelta,
        [Value for Index in range(24) for Value in (1.0 / 30.0, 1.0 / 120.0)]
    )
    assert abs(SimulatedTime - 1.0) < 0.000000001, SimulatedTime
    assert abs(GetFrameDelta(0.5) - 1.0 / 30.0) < 0.000000001
    assert GetFrameDelta(-1.0) == 0.0

    # Codex 2026-08-09: 图示红X、绿Y、蓝Z必须作为完整局部三轴参与旋转。
    IdentityAxes = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))
    AxisCases = (
        ((0.0, -1.0, 0.0), (90.0, 0.0, 0.0), (0.0, 0.0, 1.0)),
        ((1.0, 0.0, 0.0), (0.0, 90.0, 0.0), (0.0, 0.0, 1.0)),
        ((1.0, 0.0, 0.0), (0.0, 0.0, 90.0), (0.0, -1.0, 0.0)),
    )
    for Vector, Angles, Expected in AxisCases:
        Actual = RotateVectorInBasis(Vector, IdentityAxes, Angles)
        assert all(abs(Actual[Index] - Expected[Index]) < 0.000000001 for Index in range(3)), (Angles, Actual)
    LocalAxes = ((0.0, 0.0, 1.0), (0.0, 1.0, 0.0), (-1.0, 0.0, 0.0))
    Actual = RotateVectorInBasis((0.0, 0.0, 1.0), LocalAxes, (0.0, 90.0, 0.0))
    assert all(abs(Actual[Index] - (-1.0, 0.0, 0.0)[Index]) < 0.000000001 for Index in range(3)), Actual

    CapeClass = FindClass(Tree, "KnifeLightEffectCape")
    GetCapeLocatorPositions = FindMethod(CapeClass, "GetCapeLocatorPositions")
    GetCapeRotationAxes = FindMethod(CapeClass, "GetCapeRotationAxes")
    UpdatePos = FindMethod(CapeClass, "UpdatePos")
    CreateKnifeFrag = FindMethod(CapeClass, "createKnifeFrag")
    CapeRenderKnifeModel = FindMethod(CapeClass, "renderKnifeModel")
    LocatorText = ast.get_source_segment(Source, GetCapeLocatorPositions)
    RotationAxesText = ast.get_source_segment(Source, GetCapeRotationAxes)
    UpdateText = ast.get_source_segment(Source, UpdatePos)
    CreateText = ast.get_source_segment(Source, CreateKnifeFrag)
    CapeRenderText = ast.get_source_segment(Source, CapeRenderKnifeModel)
    AxisModule = ast.Module(body=[GetCapeRotationAxes], type_ignores=[])
    ast.fix_missing_locations(AxisModule)
    exec(compile(AxisModule, str(TRAIL_PATH), "exec"), Namespace)

    class FakeCape(object):
        @staticmethod
        def mix(Value1, Value2, Rate):
            return tuple(Value1[Index] + (Value2[Index] - Value1[Index]) * Rate for Index in range(3))

    RotationAxes = Namespace["GetCapeRotationAxes"](
        FakeCape(),
        (4.0, 24.0, 2.0),
        (-4.0, 24.0, 2.0),
        (0.0, 12.0, 10.0),
    )
    ExpectedAxes = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))
    for AxisIndex in range(3):
        assert all(
            abs(RotationAxes[AxisIndex][ValueIndex] - ExpectedAxes[AxisIndex][ValueIndex]) < 0.000000001
            for ValueIndex in range(3)
        ), RotationAxes
    assert "_getCapeFrameDelta(frameDelta)" in UpdateText
    assert "NowTime = sampleTime" in UpdateText
    assert "_consumeCapeSimulationSteps" not in Source
    assert "CapeSimulationRemainder" not in Source
    assert sum(isinstance(Node, ast.For) for Node in ast.walk(UpdatePos)) == 1
    # Codex 2026-08-07: 方向点必须显式读取 cape_dir，避免第三定位器列表顺序改变后指向错误。
    assert 'self.boneObj.getBonePos("cape_dir")' in LocatorText
    assert "self.boneObj.locators[2]" not in LocatorText
    assert "cape_dir_pos[0] - ShoulderCenter[0]" in UpdateText
    assert "cape_dir_pos[2] - ShoulderCenter[2]" in UpdateText
    assert "self.UpdatePos(frameDelta, sampleTime)" in CreateText
    # Codex 2026-08-09: 披风编辑预览不得再附加硬编码方向位移。
    assert 'GetMolangValue("query.mod.edit_trail_cape")' in CreateText
    assert "motion = (0, 0, 0)" in CreateText
    assert "motion = (0.1, 0.1, -0.2)" not in CreateText
    assert "self.RotateCapeVector(BaseMoveDirection, RotationAxes)" in UpdateText
    assert "self.RotateCapeVector((0.0, -1.0, 0.0), RotationAxes)" in UpdateText
    assert "self.RotateCapeVector(BaseWidthDirection, RotationAxes)" in UpdateText
    assert "RotatedBeginOffset = self.RotateCapeVector" in CreateText
    assert "RotatedEndOffset = self.RotateCapeVector" in CreateText
    assert "AxisX" in RotationAxesText and "AxisY" in RotationAxesText and "AxisZ" in RotationAxesText
    assert 'binder_args["offset"]' not in CreateText
    assert "ShoulderWidth" in CreateText
    # Codex 2026-08-07: 时间方向由共享 Shader 统一处理，披风不得分叉材质选择逻辑。
    assert "CapeMaterialMap" not in Source
    assert not any(
        isinstance(Node, ast.FunctionDef) and Node.name == "GetCapeMaterial"
        for Node in CapeClass.body
    )
    assert 'material = "arris_knife_light_normal"' in CreateText
    assert 'super_material = binder_args["material"]' in CreateText
    # Codex 2026-08-07: 回到方向实验前基线，披风直接沿用通用 progress 与颜色端点。
    assert not any(
        isinstance(Node, ast.FunctionDef) and Node.name == "GetCapeRenderProgress"
        for Node in CapeClass.body
    )
    assert "startColor, endColor = endColor, startColor" not in CapeRenderText
    assert "round(_getKnifeFragProgress(self, lastKnifeFrag), 2)" in CapeRenderText
    assert "round(_getKnifeFragProgress(self, nowKnifeFrag), 2)" in CapeRenderText

    # Codex 2026-08-06: 普通刀光继续使用原进度轴，披风修复不得外溢。
    KnifeLightClass = FindClass(Tree, "KnifeLightEffect")
    KnifeLightRenderText = ast.get_source_segment(
        Source,
        FindMethod(KnifeLightClass, "renderKnifeModel")
    )
    assert "GetCapeRenderProgress" not in KnifeLightRenderText
    assert "startColor, endColor = endColor, startColor" not in KnifeLightRenderText
    assert "round(_getKnifeFragProgress(self, lastKnifeFrag), 2)" in KnifeLightRenderText
    assert "round(_getKnifeFragProgress(self, nowKnifeFrag), 2)" in KnifeLightRenderText
    SuperClass = FindClass(Tree, "KnifeLightEffectSuper")
    SuperCreateText = ast.get_source_segment(
        Source,
        FindMethod(SuperClass, "createKnifeFrag")
    )
    SuperRenderText = ast.get_source_segment(
        Source,
        FindMethod(SuperClass, "renderKnifeModel")
    )
    assert "dir_rot = clientApi.GetRotFromDir((mx, my, mz))" in SuperCreateText
    assert "rotateZXY(offset, (-dir_rot[0], dir_rot[1], 0))" in SuperCreateText
    assert "GetCapeRenderProgress" not in SuperRenderText
    assert "startColor, endColor = endColor, startColor" not in SuperRenderText
    assert "round(_getKnifeFragProgress(self, lastKnifeFrag), 2)" in SuperRenderText
    assert "round(_getKnifeFragProgress(self, nowKnifeFrag), 2)" in SuperRenderText

    RendererClass = FindClass(Tree, "EntityAttackKnifeLightRenderer")
    UpdateCapeTrailText = ast.get_source_segment(
        Source,
        FindMethod(RendererClass, "UpdateCapeTrail")
    )
    assert '["cape_begin", "cape_end", "cape_dir"]' in UpdateCapeTrailText

    RequiredCapeLocators = {"cape_begin", "cape_end", "cape_dir"}
    for GeoPath in GEO_PATHS:
        GeoData = json.loads(GeoPath.read_text(encoding="utf-8"))
        LocatorMaps = FindLocatorMaps(GeoData)
        assert any(
            RequiredCapeLocators.issubset(set(LocatorMap))
            for LocatorMap in LocatorMaps
        ), GeoPath

    ExpectedShaderExpressions = {
        "arris_knife_light_normal": (
            "fbm(venu_pos, -TRAIL_TIME*4.0)",
            "sin(uv.x*50.0+TRAIL_TIME*5.0)",
        ),
        "arris_knife_light_mark": (
            "fbm(venu_pos, -TRAIL_TIME*4.0)",
            "sin(uv.x*50.0+TRAIL_TIME*5.0)",
        ),
        "arris_trail_undead_wave": (
            "fbm(venu_pos, (TRAIL_TIME+progress)*10.0)",
        ),
        "arris_trail_undead_smoke": (
            "-(TRAIL_TIME+progress)*1.5",
            "(TRAIL_TIME+progress)*3.0",
        ),
    }
    for MaterialName, ShaderPath in SHADER_PATHS.items():
        ShaderSource = ShaderPath.read_text(encoding="utf-8")
        assert "CAPE_REVERSE_TIME" not in ShaderSource, MaterialName
        assert ShaderSource.count("#define TRAIL_TIME (-TIME)") == 1, MaterialName
        assert "#define TRAIL_TIME TIME" not in ShaderSource, MaterialName
        for Expression in ExpectedShaderExpressions[MaterialName]:
            assert Expression in ShaderSource, (MaterialName, Expression)

        # 除宏定义外不允许业务表达式绕开 TRAIL_TIME 直接读取 TIME。
        ShaderBody = "\n".join(
            Line for Line in ShaderSource.splitlines()
            if not Line.lstrip().startswith("#")
        )
        assert re.search(r"(?<!TRAIL_)\bTIME\b", ShaderBody) is None, MaterialName

    TimeCalls = [
        Node for Node in ast.walk(UpdatePos)
        if isinstance(Node, ast.Call)
        and isinstance(Node.func, ast.Attribute)
        and isinstance(Node.func.value, ast.Name)
        and Node.func.value.id == "time"
        and Node.func.attr == "time"
    ]
    assert len(TimeCalls) == 1, len(TimeCalls)
    print("cape frame sync baseline valid: progress=original all_trail_time=reversed")


if __name__ == "__main__":
    main()
