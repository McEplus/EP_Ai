from __future__ import print_function

import sys
import types

from _common import project_root


class FakeLabel(object):
    def __init__(self):
        self.Text = ""

    def SetText(self, Value):
        self.Text = Value


class FakeControl(object):
    def __init__(self):
        self.Visible = False
        self.Alpha = 1.0
        self.Label = FakeLabel()

    def asLabel(self):
        return self.Label

    def SetVisible(self, Value):
        self.Visible = Value


class FakeGrid(object):
    def __init__(self):
        self.Cleaned = False

    def InSideGird(self):
        self.Cleaned = True


class FakeToggle(object):
    def __init__(self, Value, Callback):
        self.Value = Value
        self.Callback = Callback
        self.Disposed = False

    def setToggleState(self, Value, Exec=True):
        self.Value = Value
        if Exec:
            self.Callback(Value)

    def Dispose(self):
        self.Disposed = True


class FakeSlider(object):
    def __init__(self, Value, Callback):
        self.Value = Value
        self.Callback = Callback
        self.Disposed = False

    def GetValue(self):
        return self.Value

    def SetValue(self, Value, Exec=True):
        self.Value = Value
        if Exec:
            self.Callback(Value)

    def Dispose(self):
        self.Disposed = True


def install_fake_ui():
    ModuleName = "SwordSoulFightScripts.QingYunModLibs.UIScreen"
    Module = types.ModuleType(ModuleName)
    Module.Controls = {}
    Module.Events = {}
    Module.ScrollCalls = []
    Module.Positions = {}
    Module.Sizes = {}

    def GetControl(Path):
        if Path not in Module.Controls:
            Module.Controls[Path] = FakeControl()
        return Module.Controls[Path]

    def GetBetterUIControl(UIName, Path):
        return GetControl(Path)

    def SetVisible(UIName, Path, Value=True):
        GetControl(Path).SetVisible(Value)

    def GetCompSize(UIName, Path):
        return Module.Sizes.get(Path, (100, 20))

    def GetCompMustPosition(UIName, Path, ModName=None, CreateComp=True):
        return Module.Positions.get(Path, (0, 0))

    def GetCompAlpha(UIName, Path):
        return GetControl(Path).Alpha

    def SetCompAlpha(UIName, Path, Value=1.0):
        GetControl(Path).Alpha = Value

    def CreateGird(UIName, ScreenPath, BlockPath, Param):
        Result = {}
        for X in range(1, Param["blockNum_x"] + 1):
            for Y in range(1, Param["blockNum_y"] + 1):
                Result[str(X) + "." + str(Y)] = ScreenPath + "/Item" + str(X) + "_" + str(Y)
        return Result, FakeGrid()

    def CreateScroll_View(*Args, **Kwargs):
        Module.ScrollCalls.append((Args, Kwargs))

    def AddSuperButtonTouch(UIName, Path, State, Callback, IsSwallow=True):
        Module.Events[(Path, State)] = Callback

    def AddSuperToggleFunc(UIName, Path, Value, Callback):
        Instance = FakeToggle(Value, Callback)
        Module.Events[(Path, "Toggle")] = Instance
        return Instance

    def AddSuperSliderFunc(UIName, Path, Value, Callback, Step=0.1):
        Instance = FakeSlider(Value, Callback)
        Instance.Step = Step
        Module.Events[(Path, "Slider")] = Instance
        return Instance

    Functions = {
        "GetBetterUIControl": GetBetterUIControl,
        "SetVisible": SetVisible,
        "GetCompSize": GetCompSize,
        "GetCompMustPosition": GetCompMustPosition,
        "GetCompAlpha": GetCompAlpha,
        "SetCompAlpha": SetCompAlpha,
        "CreateGird": CreateGird,
        "CreateScroll_View": CreateScroll_View,
        "AddSuperButtonTouch": AddSuperButtonTouch,
        "AddSuperToggleFunc": AddSuperToggleFunc,
        "AddSuperSliderFunc": AddSuperSliderFunc
    }
    for Name in Functions:
        setattr(Module, Name, Functions[Name])
    sys.modules[ModuleName] = Module
    return Module


def run_test():
    BehaviorRoot = project_root() / "src" / "SwordSoul_NewERA_B"
    sys.path.insert(0, str(BehaviorRoot))
    FakeUI = install_fake_ui()

    from SwordSoulFightScripts.QingYunModLibs.ConfigUI.ConfigScreen import BaseSettingScreen
    from SwordSoulFightScripts.QingYunModLibs.ConfigUI.StateStore import MemoryStateStore

    Changes = []
    Store = MemoryStateStore({"Enabled": True, "Power": 14.0})
    Screen = BaseSettingScreen("TestUI", "/Scroll", "/Content", "/Base", Store)
    Screen.LayoutConfig = {"columns": 2, "interval_x": 30, "interval_y": -20}
    Screen.ScreenRenderConfig = [
        {
            "id": "Enabled",
            "label": "Enabled",
            "touch_type": "Toggle",
            "bind_func": Changes.append,
            "default_value": False
        },
        {
            "id": "Power",
            "label": "Power",
            "touch_type": "Slider",
            "bind_func": Changes.append,
            "default_value": 10.0,
            "min_value": 10.0,
            "max_value": 20.0,
            "step": 2.0,
            "formatter": lambda Value: "%.1f" % Value
        },
        {
            "id": "Apply",
            "label": "Apply",
            "touch_type": "Button",
            "bind_func": Changes.append,
            "default_value": False,
            "enabled_when": ("Enabled", True)
        }
    ]

    Runtime = Screen.render()
    assert set(Runtime.keys()) == set(("Enabled", "Power", "Apply"))
    assert len(Screen.chooseGirdMap) == 3
    assert FakeUI.Controls["/Content/Item2_2"].Visible is False
    assert abs(Runtime["Power"]["instance"].Value - 0.4) < 0.0001
    assert Runtime["Power"]["instance"].Step == 0.2

    MeasuredScreen = BaseSettingScreen("TestUI", "/MeasuredScroll", "/MeasuredContent", "/Base")
    MeasuredScreen.LayoutConfig = {"measure_content_bounds": True}
    MeasuredScreen.ScreenRenderConfig = [
        {"id": "First", "label": "First", "touch_type": "Button", "bind_func": None, "default_value": False},
        {"id": "Last", "label": "Last", "touch_type": "Button", "bind_func": None, "default_value": False}
    ]
    FakeUI.Positions["/MeasuredContent"] = (40, 80)
    FakeUI.Positions["/MeasuredContent/Item1_1"] = (40, 80)
    FakeUI.Positions["/MeasuredContent/Item1_2"] = (40, 137)
    FakeUI.Sizes["/MeasuredContent/Item1_1"] = (100, 48)
    FakeUI.Sizes["/MeasuredContent/Item1_2"] = (100, 48)
    MeasuredScreen.render()
    MeasuredContentSize = FakeUI.ScrollCalls[-1][0][5]
    assert MeasuredContentSize == (100, 105), MeasuredContentSize
    MeasuredScreen.unRender()

    Runtime["Power"]["instance"].SetValue(0.6)
    assert Store.Get("Power") == 16.0
    assert FakeUI.Controls[Runtime["Power"]["value_control"]].Label.Text == "16.0"

    Runtime["Enabled"]["instance"].setToggleState(False)
    assert Store.Get("Enabled") is False
    assert Runtime["Apply"]["enabled"] is False
    FakeUI.Events[(Runtime["Apply"]["control"], "Up")]("blocked")
    assert "blocked" not in Changes

    Store.Set("Power", 18.0)
    Screen.RefreshValues()
    assert abs(Runtime["Power"]["instance"].Value - 0.8) < 0.0001
    assert FakeUI.Controls[Runtime["Power"]["value_control"]].Label.Text == "18.0"

    Grid = Screen.GirdComp
    Toggle = Runtime["Enabled"]["instance"]
    Slider = Runtime["Power"]["instance"]
    Screen.unRender()
    assert Grid.Cleaned and Toggle.Disposed and Slider.Disposed
    assert not Screen.RuntimeItemMap and not Screen.chooseGirdMap

    RemoteChanges = []
    RemoteStore = MemoryStateStore({"RemoteToggle": False, "RemotePower": 0.2})
    RemoteScreen = BaseSettingScreen("TestUI", "/RemoteScroll", "/RemoteContent", "/Base", RemoteStore)
    RemoteScreen.ScreenRenderConfig = [
        {
            "id": "RemoteToggle",
            "label": "Remote Toggle",
            "touch_type": "Toggle",
            "bind_func": RemoteChanges.append,
            "default_value": False,
            "auto_save": False
        },
        {
            "id": "RemotePower",
            "label": "Remote Power",
            "touch_type": "Slider",
            "bind_func": RemoteChanges.append,
            "default_value": 0.2,
            "auto_save": False
        }
    ]
    RemoteRuntime = RemoteScreen.render()
    RemoteRuntime["RemoteToggle"]["instance"].setToggleState(True)
    assert RemoteStore.Get("RemoteToggle") is False
    assert RemoteRuntime["RemoteToggle"]["instance"].Value is True
    RemoteRuntime["RemotePower"]["instance"].SetValue(0.8)
    assert RemoteStore.Get("RemotePower") == 0.2
    assert RemoteRuntime["RemotePower"]["instance"].Value == 0.8
    assert FakeUI.Controls[RemoteRuntime["RemotePower"]["value_control"]].Label.Text == "0.8"
    assert RemoteChanges == [True, 0.8]

    RemoteStore.Set("RemoteToggle", True)
    RemoteStore.Set("RemotePower", 0.8)
    RemoteScreen.RefreshValues()
    assert RemoteRuntime["RemoteToggle"]["instance"].Value is True
    assert RemoteRuntime["RemotePower"]["instance"].Value == 0.8
    RemoteScreen.unRender()

    class FakeChooseSettingSystem(object):
        def __init__(self):
            self.Data = {"SWSOption": True}
            self.LoadingToggleComp = {}

        def getChoose(self, Key, DefaultValue=None):
            return self.Data.get(Key, DefaultValue)

        def updateChoose(self, Key, Value):
            self.Data[Key] = Value

    ChooseSettingSystem = FakeChooseSettingSystem()
    ClientModName = "SwordSoulFightScripts.QingYunModLibs.ClientMod"
    ClientMod = types.ModuleType(ClientModName)
    ClientMod.GetComponent = lambda Name: ChooseSettingSystem if Name == "ChooseSettingSystem" else None
    sys.modules[ClientModName] = ClientMod
    from SwordSoulFightScripts.UISystem.ConfigUI.SettingScreen import BaseSWSSettingScreen

    SWSScreen = BaseSWSSettingScreen("TestUI", "/Scroll", "/Content", "/Base")
    SWSScreen.ScreenRenderConfig = [{
        "id": "SWSOption",
        "label": "SWS Option",
        "touch_type": "Toggle",
        "bind_func": None,
        "default_value": False
    }]
    SWSRuntime = SWSScreen.render()
    assert SWSScreen.ChooseTypeMap["SWSOption"] == [SWSRuntime["SWSOption"]["control"], "Toggle"]
    assert ChooseSettingSystem.LoadingToggleComp["SWSOption"] == SWSRuntime["SWSOption"]["control"]
    SWSRuntime["SWSOption"]["instance"].setToggleState(False)
    assert ChooseSettingSystem.Data["SWSOption"] is False
    SWSScreen.unRender()
    print("ConfigUI tests passed")


if __name__ == "__main__":
    run_test()
