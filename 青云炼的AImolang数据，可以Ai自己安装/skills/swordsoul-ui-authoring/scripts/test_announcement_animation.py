#!/usr/bin/env python3
"""Static regression checks for announcement animations and source-aware return flow."""

from __future__ import print_function

import ast
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
ANNOUNCEMENT_PATH = ROOT / "src/SwordSoul_NewERA_B/SwordSoulFightScripts/UISystem/Announcement.py"
SETTING_PATH = ROOT / "src/SwordSoul_NewERA_B/SwordSoulFightScripts/UISystem/SettingData.py"
JSON_PATH = ROOT / "src/SwordSoul_NewERA_R/ui/Announcement.json"


def require(source, snippet):
    assert snippet in source, "missing announcement contract: %s" % snippet


def method_source(source, method_name, next_marker=None):
    start = source.index("    def %s(" % method_name)
    if next_marker:
        end = source.index(next_marker, start)
    else:
        end = source.find("\n    def ", start + 5)
        if end < 0:
            end = len(source)
    return source[start:end]


def child_map(control):
    result = {}
    for child in control.get("controls", []):
        result.update(child)
    return result


def controls_without_alpha_propagation(value, path=""):
    missing = []
    if isinstance(value, dict):
        if "controls" in value and value.get("propagate_alpha") is not True:
            missing.append(path or "/")
        for key, child in value.items():
            missing.extend(controls_without_alpha_propagation(child, path + "/" + str(key)))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            missing.extend(controls_without_alpha_propagation(child, path + "[%s]" % index))
    return missing


def main():
    source = ANNOUNCEMENT_PATH.read_text(encoding="utf-8")
    setting_source = SETTING_PATH.read_text(encoding="utf-8")
    ui = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    ast.parse(source)
    ast.parse(setting_source)

    for snippet in (
        "from ..QingYunModLibs.UIAnimation import CenteredButtonAnimator",
        "def _playOpenAnimation(self):",
        "def _playCloseAnimation(self):",
        "def _playVersionListEntrance(self):",
        "def _playContentTransition(self):",
        "def _finishVersionButtonSetup(self, RetryCount=0):",
        "def _bindVersionButtonInteractions(self):",
        "def _bindAnimatedButton(self, Path, Activate, VisualSuffixes=None, AnimateVisuals=True, CacheImmediately=True):",
        'AddSuperButtonTouch(self.uiName, Path, "Down", OnDown, True)',
        'AddSuperButtonTouch(self.uiName, Path, "Up", OnUp, True)',
        'AddSuperButtonTouch(self.uiName, Path, "Cancel", OnCancel, True)',
        'AddSuperButtonTouch(self.uiName, Path, "HoverIn", OnHoverIn, True)',
        'AddSuperButtonTouch(self.uiName, Path, "HoverOut", OnHoverOut, True)',
        "self._animateAlpha(SidePath, 1.0, 0.0, 0.18)",
        "self._playContentTransition()",
        "self._clearAnimationTimers()",
        "self._stopAnimations()",
        "self.ButtonAnimator.Destroy()",
        "self.CloseTimer = self._schedule(0.26, self._finishClose)",
        "def UnlockClose(self):",
        "_CURRENT_VIEW[0].UnlockClose()",
        'self.ReturnToMainSetting = bool(self.param.get("from_setting", False))',
        'PushUI("UISystem.MainSetting")',
        "self._schedule(0.03, self._finishVersionButtonSetup)",
        '["/default", "/hover", "/pressed", "/button_label"]',
        "MinimumWidth = max(ScrollWidth * 0.6, 8)",
        "self._schedule(0.03, self._finishVersionButtonSetup, RetryCount + 1)",
        "AnimateVisuals=True",
        "CacheImmediately=True",
        "EntranceDuration = max(0.4, 0.28 + max(len(self._versionPaths) - 1, 0) * 0.045)",
        "self._schedule(EntranceDuration, self._bindVersionButtonInteractions)",
        "if not VisualPaths and not VisualSuffixes and self.ButtonAnimator.Bind(Path):",
        'if State == "HoverOut" and VisualPath not in self.ButtonAnimator.Hovered:',
    ):
        require(source, snippet)

    open_from_setting = method_source(setting_source, "onOpenAnnouncement")
    require(open_from_setting, "MainSettingSystem.OnClose(True)")
    require(open_from_setting, 'PushUI("UISystem.Announcement", {"update": False, "from_setting": True})')

    automatic_update = method_source(setting_source, "CheckVersionUpdate")
    require(automatic_update, 'PushUI("UISystem.Announcement", {')
    require(automatic_update, '"update": True')
    require(automatic_update, '"after_close": AfterClose')
    assert "from_setting" not in automatic_update

    close_source = method_source(source, "onClose")
    assert "clientApi.PopTopUI()" not in close_source
    require(close_source, "if self.CloseLocked or self.Closing")
    finish_source = method_source(source, "_finishClose")
    require(finish_source, "clientApi.PopTopUI()")
    require(finish_source, "if ReturnToMainSetting:")
    require(finish_source, "elif AfterClose:")
    require(finish_source, "FirstRunGuideSystem.OnAnnouncementClosed")
    require(finish_source, "if GetTopUIName() != MainSettingConfig.uiDef:")

    main_screen = ui["main"]["controls"][0]["MainScreen"]
    assert main_screen.get("propagate_alpha") is True
    main_children = child_map(main_screen)
    for name in ("VersionChooseScreen", "ShowScrollView", "Close@common.button", "ReadLock"):
        assert main_children[name].get("propagate_alpha") is True, name

    version_screen = main_children["VersionChooseScreen"]
    version_children = child_map(version_screen)
    assert version_children["__default__"].get("propagate_alpha") is True
    version_scroll = version_children["VersionChooseScrollView"]
    assert version_scroll.get("propagate_alpha") is True
    choose_screen = child_map(version_scroll)["ChooseScreen"]
    assert choose_screen.get("propagate_alpha") is True
    version_button = child_map(choose_screen)["VersionChoose@common.button"]
    assert version_button.get("propagate_alpha") is True
    choose_side = child_map(version_button)["choose_side"]
    assert choose_side.get("propagate_alpha") is True

    show_screen = child_map(main_children["ShowScrollView"])["ShowScreen"]
    assert show_screen.get("propagate_alpha") is True
    read_progress = child_map(main_children["ReadLock"])["ReadProgress"]
    assert read_progress.get("propagate_alpha") is True

    render_versions = method_source(source, "_renderVersionList")
    assert "self._bindAnimatedButton(" not in render_versions
    finish_setup = method_source(source, "_finishVersionButtonSetup")
    assert "self._bindAnimatedButton(" not in finish_setup
    bind_interactions = method_source(source, "_bindVersionButtonInteractions")
    assert bind_interactions.index("UpdateScreen()") < bind_interactions.index("self._bindAnimatedButton(")
    require(bind_interactions, "LayoutReady,")
    require(bind_interactions, "False")
    version_entry = method_source(source, "_playVersionEntry")
    require(version_entry, "self._animateAlpha(Path, 1.0, 0.12, 0.2)")
    assert "_animateMove" not in version_entry
    assert "GetCompMustPosition" not in version_entry
    assert controls_without_alpha_propagation(ui) == []

    print("announcement animation regression: PASS")


if __name__ == "__main__":
    main()
