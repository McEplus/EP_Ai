# coding=utf-8
"""Focused regression checks for the adjustable in-game frame-rate HUD."""
from __future__ import print_function

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
UI_ROOT = ROOT / "src/SwordSoul_NewERA_B/SwordSoulFightScripts/UISystem"
CONTROL_PATH = UI_ROOT / "Control.py"
SETTING_PATH = UI_ROOT / "SettingData.py"
GENERAL_PATH = UI_ROOT / "GeneralScreen.py"
EDIT_PATH = UI_ROOT / "EditControlScreen.py"
CONFIG_PATH = UI_ROOT / "UIConfig.py"
JSON_PATH = ROOT / "src/SwordSoul_NewERA_R/ui/Control.json"


def method_range(source, start_name, end_name):
    start = source.index("    def %s(" % start_name)
    end = source.index("    def %s(" % end_name, start)
    return source[start:end]


def control_children(node):
    result = {}
    for item in node.get("controls", []):
        result.update(item)
    return result


def assert_alpha_chain(node, path):
    controls = node.get("controls")
    if controls is None:
        return
    assert node.get("propagate_alpha") is True, "alpha propagation break: %s" % path
    for name, child in control_children(node).items():
        assert_alpha_chain(child, path + "/" + name)


def build_runtime_harness(control_source):
    start = control_source.index("    def _SetFrameRateText(")
    end = control_source.index("    def _formatStateValue(", start)
    methods = control_source[start:end]
    methods = methods.replace(
        '    @BaseComponent.ComponentListenEvent("OnScriptTickClient")\n',
        "",
    )

    calls = []
    state = {"ui": False, "fps": 61.6}

    class Label(object):
        def asLabel(self):
            return self

        def SetText(self, text):
            calls.append(("text", text))

    def ui_mod_comp(_ui_name):
        return state["ui"]

    def get_control(_ui_name, path):
        calls.append(("lookup", path))
        return Label()

    def set_visible(_ui_name, path, visible):
        calls.append(("visible", path, visible))

    class Tool(object):
        @staticmethod
        def GetFps():
            return state["fps"]

    Generic = type("Generic", (object,), {"Tool": Tool})
    ClientApi = type("ClientApi", (object,), {"Generic": Generic})
    ControlConfig = type(
        "ControlConfig",
        (object,),
        {
            "FrameRate": "/Control/FrameRate",
            "FrameRateText": "/Control/FrameRate/Text",
        },
    )

    namespace = {
        "ClientApi": ClientApi,
        "ControlConfig": ControlConfig,
        "GetBetterUIControl": get_control,
        "SetVisible": set_visible,
        "UIModComp": ui_mod_comp,
    }
    exec("class Harness(object):\n" + methods, namespace)
    return namespace["Harness"], calls, state


def assert_runtime_lifecycle(control_source):
    Harness, calls, state = build_runtime_harness(control_source)
    hud = Harness()
    hud.uiName = "Control"
    hud.ControlReady = False
    hud.FrameRateVisible = True
    hud.FrameRateTick = 0
    hud.FrameRateLastValue = None

    # Tick-before-Create: no screen lookup, control lookup, visibility write, or text write.
    hud.OnFrameRateTick()
    assert calls == []

    # A setting callback during creation stores intent without touching the control tree.
    hud.SetFrameRateVisible(False)
    assert hud.FrameRateVisible is False
    assert calls == []

    # Create complete: visibility and the first FPS text can be applied.
    state["ui"] = True
    hud.ControlReady = True
    hud.SetFrameRateVisible(True)
    assert ("visible", "/Control/FrameRate", True) in calls
    assert ("text", "FPS 62") in calls

    # Destroyed screen: the next Tick closes the gate and performs no new control write.
    calls[:] = []
    state["ui"] = False
    hud.OnFrameRateTick()
    assert hud.ControlReady is False
    assert calls == []

    # Recreate: the new ready transition resumes normal low-frequency updates.
    state["ui"] = True
    state["fps"] = 61.6
    hud.ControlReady = True
    hud.SetFrameRateVisible(True)
    calls[:] = []
    state["fps"] = 119.7
    for _index in range(15):
        hud.OnFrameRateTick()
    assert ("text", "FPS 120") in calls


def main():
    control_source = CONTROL_PATH.read_text(encoding="utf-8")
    setting_source = SETTING_PATH.read_text(encoding="utf-8")
    general_source = GENERAL_PATH.read_text(encoding="utf-8")
    edit_source = EDIT_PATH.read_text(encoding="utf-8")
    config_source = CONFIG_PATH.read_text(encoding="utf-8")

    set_text_body = method_range(control_source, "_SetFrameRateText", "_RefreshFrameRateText")
    assert set_text_body.index("if not self.ControlReady") < set_text_body.index("GetBetterUIControl")
    tick_body = method_range(control_source, "OnFrameRateTick", "_formatStateValue")
    assert "def OnFrameRateTick(self):" in tick_body
    assert "if self.FrameRateTick < 15:" in tick_body
    assert tick_body.index("if not self.ControlReady") < tick_body.index("UIModComp")
    assert tick_body.index("self.ControlReady = False") < tick_body.index("self._RefreshFrameRateText()")
    init_body = method_range(control_source, "InitControl", "ApplyButtonConfig")
    assert init_body.index("self.ControlReady = False") < init_body.index("self.ControlReady = True")
    assert init_body.index("self.ControlReady = True") < init_body.index("self.SetFrameRateVisible")

    assert 'self.ShowFrameRate = True' in setting_source
    assert 'self.SetLocalConfig("ShowFrameRate", True)' in setting_source
    assert '"id": "ShowFrameRate"' in general_source
    assert "ControlConfig.FrameRate: ControlConfig.uiName" in edit_source
    assert edit_source.count("ControlConfig.FrameRate: {") == 2
    assert 'FrameRate = Control+"/FrameRate"' in config_source
    assert 'FrameRateText = FrameRate+"/Text"' in config_source

    data = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    root = data["main"]["controls"][0]["Control"]
    frame_rate = control_children(root)["FrameRate"]
    assert frame_rate["anchor_from"] == "top_right"
    assert frame_rate["anchor_to"] == "top_right"
    assert frame_rate["size"] == [72, 22]
    assert control_children(frame_rate)["Background"]["keep_ratio"] is False
    assert control_children(frame_rate)["Accent"]["keep_ratio"] is False
    assert_alpha_chain(frame_rate, "/Control/FrameRate")

    assert_runtime_lifecycle(control_source)
    print("frame rate HUD checks: pass")


if __name__ == "__main__":
    main()
