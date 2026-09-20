#!/usr/bin/env python3
"""Static regression checks for non-invasive MainSetting interaction animation."""

from __future__ import print_function

from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
MAIN_PATH = ROOT / "src/SwordSoul_NewERA_B/SwordSoulFightScripts/UISystem/MainSetting.py"
SCREEN_PATH = ROOT / "src/SwordSoul_NewERA_B/SwordSoulFightScripts/QingYunModLibs/UIScreen.py"
ANIMATION_PATH = ROOT / "src/SwordSoul_NewERA_B/SwordSoulFightScripts/QingYunModLibs/UIAnimation.py"


def require(source, snippet):
    assert snippet in source, "missing MainSetting animation contract: %s" % snippet


def main():
    main_source = MAIN_PATH.read_text(encoding="utf-8")
    screen_source = SCREEN_PATH.read_text(encoding="utf-8")
    animation_source = ANIMATION_PATH.read_text(encoding="utf-8")

    for snippet in (
        "class CenteredButtonAnimator(object):",
        "def GetCenteredScalePosition(BasePos, BaseSize, TargetSize):",
        "BasePos[0] + (BaseSize[0] - TargetSize[0]) * 0.5",
        "CurrentControl.SetSize(Size, True)",
        "CurrentControl.SetPosition(Pos)",
        "def HandleState(self, Path, State):",
        "def RestoreAll(self):",
        'Control.SetSize(Metric["size"], True)',
        'Control.SetPosition(Metric["pos"])',
        "def Destroy(self):",
    ):
        require(animation_source, snippet)

    for snippet in (
        "def GetRegisteredButtonRuntimeStates(uiName):",
        "def AddButtonEventObserver(uiName, Observer):",
        "def RemoveButtonEventObserver(uiName, Observer):",
        "def AddButtonRegistrationObserver(uiName, Observer):",
        "def RemoveButtonRegistrationObserver(uiName, Observer):",
        "_NotifyButtonEvent(self.NameSpace, ButtonPath, ButtonState, args)",
        "_NotifyButtonEvent(uiName, ButtonPath, ButtonState, args)",
        "_RegisterButtonRuntimeState(uiName, ButtonPath, ButtonState, IsSwallow)",
        "def AddVisualButtonTouch(uiName, ButtonPath, ButtonState, BackFunc, IsSwallow=True):",
        "_RegisterButtonRuntimeState(uiName, ButtonPath, ButtonState, IsSwallow, True)",
        "_ClearButtonRuntime(self.NameSpace)",
    ):
        require(screen_source, snippet)

    for snippet in (
        "from ..QingYunModLibs.UIAnimation import CenteredButtonAnimator",
        "def StartInteractionAnimations(self):",
        "def StopInteractionAnimations(self):",
        "def _TryBindInteractionAnimation(self, Path, AllowRetry=True):",
        "Exclusions.update(ItemChooseSystemObj.ChooseSlotMap.keys())",
        "AddButtonEventObserver(self.uiName, self._OnInteractionButtonEvent)",
        "AddButtonRegistrationObserver(self.uiName, self._OnInteractionButtonRegistered)",
        "self.InteractionAnimator.HandleState(VisualPath, State)",
        'for State in ["Down", "Cancel", "HoverIn", "HoverOut"]:',
        'for Suffix in ["/default", "/hover", "/pressed", "/button_label"]:',
        "self.InteractionVisualPaths[Path] = VisualPaths",
    ):
        require(main_source, snippet)

    # Visual augmentation must never install or replace the existing business Up callback.
    bind_start = main_source.index("    def _TryBindInteractionAnimation")
    bind_end = main_source.index("\n    def _OnInteractionButtonRegistered", bind_start)
    bind_source = main_source[bind_start:bind_end]
    assert 'for State in ["Down", "Cancel", "HoverIn", "HoverOut"]:' in bind_source
    assert 'for State in ["Down", "Up"' not in bind_source
    assert 'AddSuperButtonTouch(self.uiName, Path, "Up"' not in bind_source
    assert "AddSuperButtonTouch(self.uiName, Path, State" not in bind_source
    assert "AddVisualButtonTouch(self.uiName, Path, State" in bind_source
    assert "self.InteractionAnimator.Bind(Path)" not in bind_source

    visual_start = screen_source.index("def AddVisualButtonTouch")
    visual_end = screen_source.index("\n\ndef AddSuperButton", visual_start)
    visual_source = screen_source[visual_start:visual_end]
    assert "SetTouchButtonState" not in visual_source
    assert "TouchScrollViewState" not in visual_source
    assert '"Up":' not in visual_source

    button_control_start = screen_source.index("    def Button_Control")
    button_control_end = screen_source.index("\n\ndef ReloadButtonBack", button_control_start)
    button_control_source = screen_source[button_control_start:button_control_end]
    assert button_control_source.count("BackFunc(*args)") == 1

    on_close_start = main_source.index("    def OnClose(self, Super=False):")
    on_close_end = main_source.index("\n    def PlayerCloseAnimation", on_close_start)
    assert "self.StopInteractionAnimations()" in main_source[on_close_start:on_close_end]
    on_destroy_start = main_source.index("    def OnDestroy(self):")
    on_destroy_end = main_source.index("\n\n\n@ClientMod.LoadingComponent", on_destroy_start)
    assert "self.StopInteractionAnimations()" in main_source[on_destroy_start:on_destroy_end]

    # Existing screen entrance/exit and selected-slot animation remain authoritative.
    for method in (
        "def PlayerOpenAnimation(self):",
        "def PlayerCloseAnimation(self):",
        "def PlayChooseSlotAnimation(self, Comp):",
    ):
        require(main_source, method)

    print("MainSetting interaction animation regression: PASS")


if __name__ == "__main__":
    main()
