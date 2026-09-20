# coding=utf-8
"""Mob 到 SWS 本地粒子入口的短参数补齐与实体归属回归。"""

import ast
import copy
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[4]
MOB_RENDER_PATH = (
    PROJECT_ROOT / "src" / "SwordSoul_NewERA_B" / "SwordSoulMobFightScripts" / "Render" / "MobRenderClient.py"
)


def ReadTree():
    return ast.parse(MOB_RENDER_PATH.read_text(encoding="utf-8-sig"))


def FindClass(Tree, Name):
    return next(Node for Node in Tree.body if isinstance(Node, ast.ClassDef) and Node.name == Name)


def FindMethod(ClassNode, Name):
    return next(Node for Node in ClassNode.body if isinstance(Node, ast.FunctionDef) and Node.name == Name)


class FakeParticleComponent(object):
    def __init__(self):
        self.Calls = []

    def _playParticle(self, Data):
        self.Calls.append(("_playParticle", Data))
        return Data

    def _playParticleBind(self, Data):
        self.Calls.append(("_playParticleBind", Data))
        return Data


class FakeEffectClientMod(object):
    def __init__(self):
        self.Component = FakeParticleComponent()

    def GetComponent(self, ComponentName):
        return self.Component


class FakeClientApi(object):
    def __init__(self):
        self.EffectClientMod = FakeEffectClientMod()

    def ImportModule(self, ModuleName):
        return self.EffectClientMod


def BuildNormalizeHarness(RenderClass):
    NormalizeMethod = copy.deepcopy(FindMethod(RenderClass, "_normalize_sws_particle_local_data"))
    CallMethod = copy.deepcopy(FindMethod(RenderClass, "_call_sws_particle_local"))
    HarnessClass = ast.ClassDef(
        name="ParticleBridgeHarness",
        bases=[ast.Name(id="object", ctx=ast.Load())],
        keywords=[],
        body=[NormalizeMethod, CallMethod],
        decorator_list=[],
    )
    Module = ast.fix_missing_locations(ast.Module(body=[HarnessClass], type_ignores=[]))
    ClientApiHarness = FakeClientApi()
    Namespace = {"clientApi": ClientApiHarness, "mob_log": lambda *Args: None}
    exec(compile(Module, str(MOB_RENDER_PATH), "exec"), Namespace)
    return Namespace["ParticleBridgeHarness"], ClientApiHarness


def AssertShortPayloadsArePadded(RenderClass):
    HarnessClass, ClientApiHarness = BuildNormalizeHarness(RenderClass)
    Harness = HarnessClass()
    # Codex 2026-08-03: 直接复现截图中的三项/四项短参数，必须补成 SWS 固定六项契约。
    assert Harness._normalize_sws_particle_local_data(
        "_playParticle", ["arris:dimensional_sever_round", "stale-mob", "root_locator"], "current-mob"
    ) == ["arris:dimensional_sever_round", "current-mob", "root_locator", (0, 0, 0), (0, 0, 0), 0.0]
    assert Harness._normalize_sws_particle_local_data(
        "_playParticle", ["arris:boom_dirt", "stale-mob", "root_locator", (1, 2, 3)], "current-mob"
    ) == ["arris:boom_dirt", "current-mob", "root_locator", (1, 2, 3), (0, 0, 0), 0.0]

    Variables = {"variable.fly_speed": 2.0}
    assert Harness._normalize_sws_particle_local_data(
        "_playParticle", ["arris:test", "stale-mob", None, None, None, None, Variables], "current-mob"
    ) == ["arris:test", "current-mob", "", (0, 0, 0), (0, 0, 0), 0.0, Variables]
    assert Harness._normalize_sws_particle_local_data(
        "_playParticleBind", ["arris:test", "stale-mob", "root", (0, 0, 0), (0, 0, 0), 1.0, Variables], "current-mob"
    ) == ["arris:test", "current-mob", "root", (0, 0, 0), (0, 0, 0), 1.0]

    # Codex 2026-08-03: 覆盖截图堆栈最后一跳，确认真正调用 SWS 私有入口前已经完成补参。
    Result = Harness._call_sws_particle_local(
        "_playParticle", ["arris:dimensional_sever_smoke", "stale-mob", "root_locator"], "current-mob"
    )
    assert Result == ["arris:dimensional_sever_smoke", "current-mob", "root_locator", (0, 0, 0), (0, 0, 0), 0.0]
    assert ClientApiHarness.EffectClientMod.Component.Calls[-1] == ("_playParticle", Result)


def AssertGenericRoutesPassEventEntity(RenderClass):
    CallCount = 0
    for MethodName in ("_play_localized_sws_effect", "_play_localized_attack_effect"):
        MethodNode = FindMethod(RenderClass, MethodName)
        Calls = [
            Node for Node in ast.walk(MethodNode)
            if isinstance(Node, ast.Call)
            and isinstance(Node.func, ast.Attribute)
            and Node.func.attr == "_call_sws_particle_local"
            and len(Node.args) >= 2
            and isinstance(Node.args[1], ast.Name)
            and Node.args[1].id == "args"
        ]
        assert len(Calls) == 2, (MethodName, len(Calls))
        for CallNode in Calls:
            assert len(CallNode.args) == 3
            assert isinstance(CallNode.args[2], ast.Name) and CallNode.args[2].id == "entityId"
        CallCount += len(Calls)
    return CallCount


def Main():
    RenderClass = FindClass(ReadTree(), "MobFightRenderSystem")
    AssertShortPayloadsArePadded(RenderClass)
    CallCount = AssertGenericRoutesPassEventEntity(RenderClass)
    print("mob particle bridge valid: padded_short_payloads=2 event_owned_routes=%d" % CallCount)


if __name__ == "__main__":
    Main()
