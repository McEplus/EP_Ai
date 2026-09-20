#!/usr/bin/env python3
"""Static regression checks for the tutorial screen animation contract."""

from __future__ import print_function

import ast
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
PY_PATH = ROOT / "src/SwordSoul_NewERA_B/SwordSoulFightScripts/UISystem/TutorialScreen.py"
ANIMATION_PATH = ROOT / "src/SwordSoul_NewERA_B/SwordSoulFightScripts/QingYunModLibs/UIAnimation.py"
JSON_PATH = ROOT / "src/SwordSoul_NewERA_R/ui/TutorialScreen.json"


def require(source, snippet):
    assert snippet in source, "missing animation contract: %s" % snippet


def main():
    source = PY_PATH.read_text(encoding="utf-8")
    animation_source = ANIMATION_PATH.read_text(encoding="utf-8")
    ui = json.loads(JSON_PATH.read_text(encoding="utf-8"))

    for snippet in (
        "def _playOpenAnimation(self):",
        "def _playCloseAnimation(self):",
        "from ..QingYunModLibs.UIAnimation import CenteredButtonAnimator",
        "def _bindAnimatedButton(self, Path, Activate):",
        "def _playContentTransition(self, Direction):",
        "def _renderSectionState(self, Animate=False):",
        'AddSuperButtonTouch(self.uiName, Path, "Down", OnDown, True)',
        'AddSuperButtonTouch(self.uiName, Path, "Up", OnUp, True)',
        'AddSuperButtonTouch(self.uiName, Path, "Cancel", OnCancel, True)',
        'AddSuperButtonTouch(self.uiName, Path, "HoverIn", OnHoverIn, True)',
        'AddSuperButtonTouch(self.uiName, Path, "HoverOut", OnHoverOut, True)',
        "self._renderPage(True, -1)",
        "self._renderPage(True, 1)",
        'u"%02d / %02d"',
        "self._renderAll(False, True, Direction)",
        "self._clearAnimationTimers()",
        "self._stopAnimations()",
        "self.CloseTimer = self._schedule(0.26, self._finishClose)",
        "self.ButtonAnimator.HandleState(Path, \"Down\")",
        "self.ButtonAnimator.HandleState(Path, \"Up\")",
        "self._bindAnimatedButton(Path, self.OnChooseSection)",
        "self._bindAnimatedButton(self.cfg.StartPractice, self.OnStartPractice)",
        "self._schedule(0.40, self._enableInteraction)",
        "def _enableInteraction(self):",
        "UiNode.UpdateScreen()",
        "if not self.InteractionReady or self.Closing:",
        "self._lockInteraction(0.24)",
    ):
        require(source, snippet)

    for snippet in (
        "def GetCenteredScalePosition(BasePos, BaseSize, TargetSize):",
        "class CenteredButtonAnimator(object):",
        "CurrentControl.SetSize(Size, True)",
        "CurrentControl.SetPosition(Pos)",
        "if not Size or Size[0] <= 4 or Size[1] <= 4:",
    ):
        require(animation_source, snippet)

    assert "ButtonAnchors" not in source
    tree = ast.parse(animation_source)
    center_node = next(
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "GetCenteredScalePosition"
    )
    namespace = {}
    isolated = ast.Module(body=[center_node], type_ignores=[])
    exec(compile(ast.fix_missing_locations(isolated), str(PY_PATH), "exec"), namespace)
    center_scale_pos = namespace["GetCenteredScalePosition"]
    base_pos = (100.0, 80.0)
    base_size = (120.0, 40.0)
    target_size = (108.0, 36.0)
    target_pos = center_scale_pos(base_pos, base_size, target_size)
    base_center = (
        base_pos[0] + base_size[0] * 0.5,
        base_pos[1] + base_size[1] * 0.5,
    )
    target_center = (
        target_pos[0] + target_size[0] * 0.5,
        target_pos[1] + target_size[1] * 0.5,
    )
    assert target_center == base_center, (base_center, target_center)

    close_start = source.index("    def OnClose(self, Args=None):")
    close_end = source.index("\n\n\nclass UIScreen", close_start)
    close_source = source[close_start:close_end]
    assert "clientApi.PopTopUI()" not in close_source

    sections_start = source.index("    def _renderSections(self, Animate=False):")
    sections_end = source.index("\n    def _renderPage", sections_start)
    sections_source = source[sections_start:sections_end]
    assert sections_source.index("UpdateScreen()") < sections_source.index(
        "self._bindAnimatedButton(Path, self.OnChooseSection)"
    )

    main_screen = ui["main"]["controls"][0]["Control"]["controls"][0]["MainScreen"]
    assert main_screen.get("propagate_alpha") is True
    child_map = {}
    for child in main_screen["controls"]:
        child_map.update(child)
    for name in ("Header", "RootScreen", "ContentScreen", "ChapterScreen"):
        assert child_map[name].get("propagate_alpha") is True, name

    content_screen = child_map["ContentScreen"]
    content_children = {}
    for child in content_screen["controls"]:
        content_children.update(child)
    assert content_screen["size"][1] == "65%+0px"
    assert content_children["DetailScrollView"]["size"][1] == "38%+0px"
    assert content_children["DetailScrollView"].get("propagate_alpha") is True
    detail_content = content_children["DetailScrollView"]["controls"][0]["DetailContent"]
    assert detail_content.get("propagate_alpha") is True
    assert content_children["InputHint"]["offset"][1] == "-9%+0px"
    assert content_children["StartPractice@TutorialScreen.nav_button"]["offset"][1] == "-3%+0px"
    assert content_children["Previous@TutorialScreen.nav_button"]["offset"][1] == "-3%+0px"
    assert content_children["Next@TutorialScreen.nav_button"]["offset"][1] == "-3%+0px"
    assert "PageCounterBackground" not in content_children
    assert content_children["PageCounter"]["text"] == "01 / 01"
    assert content_children["PageCounter"]["font_scale_factor"] == 0.72
    assert content_children["PageCounter"]["text_alignment"] == "right"
    assert child_map["ChapterScreen"]["offset"][1] == "-4%+0px"

    for template_name in (
        "chapter_button@common.button",
        "nav_button@common.button",
        "section_button@common.button",
    ):
        assert ui[template_name].get("propagate_alpha") is True, template_name

    assert ui["guide_overlay"].get("propagate_alpha") is True
    guide_children = {
        name.split("@", 1)[0]: value
        for entry in ui["guide_overlay"]["controls"]
        for name, value in entry.items()
    }
    assert guide_children["ModeBanner"].get("propagate_alpha") is True
    assert all(
        value.get("propagate_alpha") is True
        for entry in guide_children["ModeBanner"]["controls"]
        for value in entry.values()
    )

    print("tutorial animation regression: PASS")


if __name__ == "__main__":
    main()
