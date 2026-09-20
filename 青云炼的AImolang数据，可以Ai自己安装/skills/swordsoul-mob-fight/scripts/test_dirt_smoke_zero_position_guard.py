# coding=utf-8
"""Sprint/Dodge 尘土轨迹零坐标防护的静态与行为回归检查。"""

import ast
import copy
import math
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[4]
FIGHT_EFFECT_PATH = PROJECT_ROOT / "src" / "SwordSoul_NewERA_B" / "SwordSoulFightScripts" / "EffectSystem" / "Fight.py"
METHOD_NAMES = {
    "_IsValidDirtSmokeTrailPos",
    "_GetDirtSmokeTrailWorldPos",
    "_GetSprintDirtSmokeEmissionPosList",
}


class FakePositionSource(object):
    BonePos = (0, 0, 0)
    FootPos = (0, 0, 0)


class FakeBaseApi(object):
    @staticmethod
    def GetBonePos(entityId, locator):
        return FakePositionSource.BonePos


class FakeAttribute(object):
    @staticmethod
    def GetFootPos(entityId):
        return FakePositionSource.FootPos

    @staticmethod
    def GetRot(entityId):
        return (0, 0)


class FakeEntity(object):
    Attribute = FakeAttribute


class FakeClientApi(object):
    Entity = FakeEntity


class FakeAlgorithms(object):
    @staticmethod
    def rotateZXY(offset, rotate):
        return offset

    @staticmethod
    def VectorAdd(left, right):
        return tuple(float(left[Index]) + float(right[Index]) for Index in range(3))


class FakeQuality(object):
    QUALITY_MEDIUM = 1

    @staticmethod
    def GetQualityLevel(Category):
        # Codex 2026-08-05: 零点保护专项保持高档采样间距，隔离验证目标不受质量档位干扰。
        return 2


def BuildHarness():
    Tree = ast.parse(FIGHT_EFFECT_PATH.read_text(encoding="utf-8-sig"))
    EffectClass = next(
        Node for Node in Tree.body
        if isinstance(Node, ast.ClassDef) and Node.name == "AttackEffectSystem"
    )
    Methods = [
        copy.deepcopy(Node) for Node in EffectClass.body
        if isinstance(Node, ast.FunctionDef) and Node.name in METHOD_NAMES
    ]
    assert {Method.name for Method in Methods} == METHOD_NAMES
    HarnessClass = ast.ClassDef(
        name="DirtSmokeHarness",
        bases=[ast.Name(id="object", ctx=ast.Load())],
        keywords=[],
        body=Methods,
        decorator_list=[],
    )
    HarnessModule = ast.fix_missing_locations(ast.Module(body=[HarnessClass], type_ignores=[]))
    Namespace = {
        "math": math,
        "BaseApi": FakeBaseApi,
        "ClientApi": FakeClientApi,
        "CommonAlgorithms": FakeAlgorithms,
        "Quality": FakeQuality,
    }
    exec(compile(HarnessModule, str(FIGHT_EFFECT_PATH), "exec"), Namespace)
    Harness = Namespace["DirtSmokeHarness"]
    Harness.SprintDirtSmokeMaxSampleSpacing = 0.5
    Harness.DodgeDirtSmokeMaxSampleSpacing = 0.2
    return Harness()


def AssertZeroBoneFallsBackToFoot(Harness):
    FakePositionSource.BonePos = (0, 0, 0)
    FakePositionSource.FootPos = (12, 64, 8)
    Position = Harness._GetDirtSmokeTrailWorldPos("mob", "waist", (1, 0, -2))
    assert Position == (13.0, 64.0, 6.0), Position


def AssertAllZeroDoesNotEnterHistory(Harness):
    FakePositionSource.BonePos = (0, 0, 0)
    FakePositionSource.FootPos = (0, 0, 0)
    EffectData = {
        "locator": "waist",
        "offset": (0, 0, 0),
        "effect_kind": "sprint",
        "last_position": None,
    }
    assert Harness._GetSprintDirtSmokeEmissionPosList("mob", EffectData) is None
    assert EffectData["last_position"] is None

    FakePositionSource.BonePos = (20, 64, 20)
    Samples = Harness._GetSprintDirtSmokeEmissionPosList("mob", EffectData)
    assert Samples == [(20.0, 64.0, 20.0)], Samples
    assert EffectData["last_position"] == (20.0, 64.0, 20.0)


def AssertZeroDoesNotOverwriteValidHistory(Harness):
    LastPosition = (10.0, 64.0, 10.0)
    EffectData = {
        "locator": "waist",
        "offset": (0, 0, 0),
        "effect_kind": "dodge",
        "last_position": LastPosition,
    }
    FakePositionSource.BonePos = (0, 0, 0)
    FakePositionSource.FootPos = (0, 0, 0)
    assert Harness._GetSprintDirtSmokeEmissionPosList("mob", EffectData) is None
    assert EffectData["last_position"] == LastPosition


def Main():
    # Codex 2026-08-03: 同时验证首帧零坐标、脚底回退和历史坐标不被污染。
    Harness = BuildHarness()
    AssertZeroBoneFallsBackToFoot(Harness)
    AssertAllZeroDoesNotEnterHistory(Harness)
    AssertZeroDoesNotOverwriteValidHistory(Harness)
    print("dirt smoke zero-position guard valid: fallback=1 initial_guard=1 history_guard=1")


if __name__ == "__main__":
    Main()
