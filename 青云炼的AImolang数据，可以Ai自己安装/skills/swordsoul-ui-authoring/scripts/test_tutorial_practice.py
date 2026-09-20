#!/usr/bin/env python3
"""Static regression checks for tutorial illustrations and practical guidance."""

from __future__ import print_function

import ast
import json
import runpy
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
UI_DIR = ROOT / "src/SwordSoul_NewERA_B/SwordSoulFightScripts/UISystem"
RESOURCE_DIR = ROOT / "src/SwordSoul_NewERA_R"


def require(source, snippet):
    assert snippet in source, "missing tutorial practice contract: %s" % snippet


def child_map(control):
    result = {}
    for child in control.get("controls", []):
        result.update(child)
    return result


def load_catalog():
    path = UI_DIR / "TutorialCatalog.py"
    return runpy.run_path(str(path))["TUTORIAL_CATALOG"]


def load_wrap_text():
    """抽取运行时换行函数，直接回归UTF-8字节串与中文边界。"""
    path = UI_DIR / "TutorialPractice.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    practice_class = next(
        node for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "TutorialPracticeSystem"
    )
    wrap_function = next(
        node for node in practice_class.body
        if isinstance(node, ast.FunctionDef) and node.name == "_wrapText"
    )
    module = ast.Module(body=[wrap_function], type_ignores=[])
    namespace = {"_TEXT_TYPE": str}
    exec(compile(ast.fix_missing_locations(module), str(path), "exec"), namespace)
    return namespace["_wrapText"]


def load_button_focus_helpers():
    """直接回归不同 HUD 缩放、位置与屏幕边缘下的高亮几何。"""
    path = UI_DIR / "TutorialPractice.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names = {"_GetButtonFocusRect", "_GetButtonFocusPromptSide"}
    functions = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in names]
    namespace = {}
    module = ast.Module(body=functions, type_ignores=[])
    exec(compile(ast.fix_missing_locations(module), str(path), "exec"), namespace)
    return namespace


def load_reentry_runtime():
    path = UI_DIR / "TutorialPractice.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    function_names = {"IsTutorialModeActive", "BlockTutorialBookEntry", "TryOpenTutorialBook"}
    functions = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in function_names]
    practice_class = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "TutorialPracticeSystem")
    methods = [
        node for node in practice_class.body
        if isinstance(node, ast.FunctionDef) and node.name in {"IsActive", "_setTutorialBookEntryVisible", "Start"}
    ]
    runtime_class = ast.ClassDef(
        name="RuntimePracticeProbe",
        bases=[],
        keywords=[],
        body=methods,
        decorator_list=[],
    )
    namespace = {}
    module = ast.Module(body=functions + [runtime_class], type_ignores=[])
    exec(compile(ast.fix_missing_locations(module), str(path), "exec"), namespace)
    return namespace


def main():
    tutorial_source = (UI_DIR / "TutorialScreen.py").read_text(encoding="utf-8")
    practice_source = (UI_DIR / "TutorialPractice.py").read_text(encoding="utf-8")
    control_source = (UI_DIR / "Control.py").read_text(encoding="utf-8")
    setting_source = (UI_DIR / "MainSetting.py").read_text(encoding="utf-8")
    emoji_source = (UI_DIR / "EmojiUi.py").read_text(encoding="utf-8")
    emoji_button_source = (UI_DIR / "EmojiButton.py").read_text(encoding="utf-8")
    team_source = (ROOT / "src/SwordSoul_NewERA_B/SwordSoulFightScripts/TeamSystem/Client.py").read_text(encoding="utf-8")
    guide_document = (ROOT / "剑魂教程引导.md").read_text(encoding="utf-8")

    for snippet in (
        "self._bindAnimatedButton(self.cfg.StartPractice, self.OnStartPractice)",
        "def _renderIllustration(self, Page):",
        "def _renderPracticeState(self, Page):",
        "def OnStartPractice(self, Args=None):",
        "PracticeSystem.EnterAfterBook()",
        "TutorialPractice.BlockTutorialBookEntry(True)",
        'self.SetLocalConfig("PracticedPages", True, False)',
    ):
        require(tutorial_source, snippet)

    for snippet in (
        "class TutorialPracticeSystem(BaseComponent):",
        "Text = Text.decode(\"utf-8\", \"replace\")",
        "def OnSurfaceReady(self, Surface):",
        "def OnSurfaceClosed(self, Surface):",
        "if not self.SurfaceReady.get(Surface, False):",
        "if not UIModComp(Config[\"ui_name\"]):",
        "Token != self.SessionToken",
        "def ReplayPending():",
        "def IsExpecting(self, Action):",
        "def IsTutorialModeActive():",
        "def BlockTutorialBookEntry(ShowMessage=True):",
        "def TryOpenTutorialBook():",
        "def IsActive(self):",
        "if self.IsActive():",
        "self._setTutorialBookEntryVisible(False)",
        "self._setTutorialBookEntryVisible(True)",
        "TryOpenTutorialBook()",
        '"EmojiUi": False',
        'Surface == "EmojiUi"',
        "def _getRenderSurface(self):",
        'PushUI("UISystem.TutorialScreen")',
        "from ..SwordSoulClient import OnOpenSettings",
        "not TeamClientSystem.CanOpenMainSetting()",
        "ProgressSystem.MarkPracticed(self.ActivePageId)",
        "def _updateActualButtonFocus(self, Pulse=False):",
        "UIMod.GetCompMustPosition(TargetUiName, TargetPath, CreateComp=False)",
        "UIMod.GetCompSize(TargetUiName, TargetPath)",
        "UIMod.SetCompMustPosition(ControlConfig.uiName, ControlConfig.TutorialButtonFocus, FocusPos)",
        "self.ButtonFocusTimer = CreateTimer(0.12, self._tickButtonFocus, True)",
        "self.ButtonFocusToken != self.SessionToken",
        '"emote_open": (EmojiButtonConfig.uiName, EmojiButtonConfig.EmojiButton)',
        "not self.ButtonTargetReady.get(TargetUiName, False)",
        'getattr(TargetScreen, "TutorialButtonReady", False)',
        '@BaseComponent.ComponentListenEvent("OnKeyPressInGame")',
        '@BaseComponent.ComponentListenEvent("OnGamepadKeyPressClientEvent")',
        "if self.WaitingForContinue:",
        "self.ContinueBriefing()",
    ):
        require(practice_source, snippet)
    assert "PerspChangeClientEvent" not in practice_source
    assert '"perspective_change"' not in practice_source
    assert "切换人称" not in guide_document
    assert "动作优化 ↔ 完整战斗" in guide_document
    assert 'TutorialPracticeSystem = GetComponent("TutorialPracticeSystem")' in team_source
    assert "TutorialPracticeSystem.IsActive()" in team_source
    target_callback = team_source[team_source.index("    def _OnTargetStatus"):]
    assert "if not self._CanUseTargetHud():" in target_callback

    # Codex 2026-07-19: 旧实现会在第34字节截到“中”的0xE6首字节并触发UnicodeDecodeError。
    wrap_text = load_wrap_text()
    boundary_text = "A" * 33 + "中文提示继续显示"
    wrapped_boundary = wrap_text(None, boundary_text.encode("utf-8"), 34)
    assert wrapped_boundary.replace("\n", "") == boundary_text
    assert all(len(line) <= 34 for line in wrapped_boundary.split("\n"))
    assert "�" not in wrapped_boundary
    assert wrap_text(None, "纯中文教程提示".encode("utf-8"), 4) == "纯中文教\n程提示"
    assert wrap_text(None, b"ASCII tutorial cue", 5) == "ASCII\n tuto\nrial \ncue"
    assert wrap_text(None, b"broken:\xe6", 20) == "broken:�"

    focus_helpers = load_button_focus_helpers()
    focus_rect = focus_helpers["_GetButtonFocusRect"]
    prompt_side = focus_helpers["_GetButtonFocusPromptSide"]
    # 默认、放大和缩小按钮都由实际尺寸派生，不能退回固定 38/51 像素布局。
    assert focus_rect((100, 50), (40, 40)) == ((93.6, 43.6), (52.8, 52.8))
    assert focus_rect((100, 50), (120, 90)) == ((90.0, 40.0), (140.0, 110.0))
    assert focus_rect((100, 50), (16, 16)) == ((96.0, 46.0), (24.0, 24.0))
    assert prompt_side((450, 50), (50, 50), (500, 250)) == "left"
    assert prompt_side((0, 50), (50, 50), (500, 250)) == "right"
    assert prompt_side((225, 50), (50, 50), (500, 250)) == "above"
    assert prompt_side((225, 0), (50, 50), (500, 250)) == "below"

    reentry_runtime = load_reentry_runtime()
    messages = []
    pushes = []
    active_system = type("ActivePractice", (), {"IsActive": lambda self: True})()
    reentry_runtime["GetComponent"] = lambda name: active_system
    message_api = type("MessageApi", (), {"SetTipMessage": staticmethod(messages.append)})
    reentry_runtime["ClientApi"] = type("ClientApiProbe", (), {"World": type("WorldProbe", (), {"Message": message_api})})
    reentry_runtime["PushUI"] = pushes.append
    reentry_runtime["TUTORIAL_REENTRY_MESSAGE"] = u"教学进行中"
    assert reentry_runtime["IsTutorialModeActive"]() is True
    assert reentry_runtime["BlockTutorialBookEntry"](True) is True
    assert reentry_runtime["TryOpenTutorialBook"]() is False
    assert pushes == [] and messages == [u"教学进行中", u"教学进行中"]
    inactive_system = type("InactivePractice", (), {"IsActive": lambda self: False})()
    reentry_runtime["GetComponent"] = lambda name: inactive_system
    assert reentry_runtime["TryOpenTutorialBook"]() is True
    assert pushes == ["UISystem.TutorialScreen"]

    runtime_probe = reentry_runtime["RuntimePracticeProbe"]()
    runtime_probe.ActivePageId = "armor_training"
    runtime_probe.SurfaceReady = {"MainSetting": True}
    cancel_calls = []
    runtime_probe.Cancel = lambda show_message: cancel_calls.append(show_message)
    start_method = reentry_runtime["RuntimePracticeProbe"].Start
    start_method.__globals__["ClientApi"] = reentry_runtime["ClientApi"]
    start_method.__globals__["TUTORIAL_REENTRY_MESSAGE"] = u"教学进行中"
    assert start_method(runtime_probe, "stiff_training", {"steps": [{}]}) is False
    assert cancel_calls == []
    entry_visibility = []
    visibility_method = reentry_runtime["RuntimePracticeProbe"]._setTutorialBookEntryVisible
    visibility_method.__globals__["GetComponent"] = lambda name: type("ReadySetting", (), {"Ready": True})()
    visibility_method.__globals__["SetVisible"] = lambda ui_name, path, visible: entry_visibility.append((ui_name, path, visible))
    visibility_method.__globals__["MainSettingConfig"] = type(
        "MainSettingConfigProbe", (), {"uiName": "MainSetting", "Tutorial": "/Control/Tutorial"}
    )
    visibility_method(runtime_probe, False)
    assert entry_visibility == [("MainSetting", "/Control/Tutorial", False)]

    for action in (
        "attack_down", "attack_up", "defense_down", "defense_up",
        "dodge_down", "dodge_up", "hook_down", "hook_up",
        "skill_down", "skill_up", "swap_hand", "back_item", "fight_mode",
    ):
        require(control_source, 'NotifyTutorialAction("%s"' % action)
    require(control_source, 'TutorialPracticeSystem.OnSurfaceReady("Control")')
    require(control_source, 'TutorialPracticeSystem.OnSurfaceClosed("Control")')
    fight_toggle_start = control_source.index("def OnToggleFightMode(args, State=None):")
    fight_toggle_end = control_source.index("KeyBoardClient.AddKeyFuncBind", fight_toggle_start)
    fight_toggle_source = control_source[fight_toggle_start:fight_toggle_end]
    assert fight_toggle_source.index("if State is None:") < fight_toggle_source.index(
        'NotifyTutorialAction("fight_mode"'
    )

    for snippet in (
        'self.Ready = False',
        'self.Ready = True',
        'TutorialPracticeSystem.OnSurfaceReady("MainSetting")',
        'TutorialPracticeSystem.OnSurfaceClosed("MainSetting")',
        'NotifyTutorialAction("settings_slot", index)',
        "TryOpenTutorialBook()",
        '"settings_general_control" if ChooseLabel == u"操作设置"',
        '"settings_detail_skill" if ChooseLabel == u"技能配备"',
    ):
        require(setting_source, snippet)
    assert 'PushUI("UISystem.TutorialScreen")' not in setting_source
    for snippet in (
        'NotifyTutorialAction("emote_play", slotIdx)',
        'NotifyTutorialAction("emote_invalid", slotIdx)',
        'PracticeSystem.OnSurfaceReady("EmojiUi")',
        'PracticeSystem.OnSurfaceClosed("EmojiUi")',
        'self.TutorialReady = True',
    ):
        require(emoji_source, snippet)
    wheel_start = emoji_source.index("    def OnWheelTouchUp(self):")
    wheel_end = emoji_source.index("\n\n\n@AddButton", wheel_start)
    wheel_source = emoji_source[wheel_start:wheel_end]
    assert wheel_source.index("if _playEmoji(slotIdx):") < wheel_source.index("clientApi.PopTopUI()")
    assert wheel_source.index("clientApi.PopTopUI()") < wheel_source.index('NotifyTutorialAction("emote_invalid"')
    for snippet in (
        "@AddCreateFunc(EmojiButtonConfig.uiName)",
        "Screen.TutorialButtonReady = True",
        "PracticeSystem.OnButtonTargetReady(EmojiButtonConfig.uiName)",
        'UIMod.UIModComp(EmojiButtonConfig.uiName)',
        'ClientMod.GetComponent("TutorialPracticeSystem")',
    ):
        require(emoji_button_source, snippet)

    tutorial_ui = json.loads((RESOURCE_DIR / "ui/TutorialScreen.json").read_text(encoding="utf-8"))
    control_ui = json.loads((RESOURCE_DIR / "ui/Control.json").read_text(encoding="utf-8"))
    setting_ui = json.loads((RESOURCE_DIR / "ui/MainSetting.json").read_text(encoding="utf-8"))
    emoji_ui = json.loads((RESOURCE_DIR / "ui/EmojiUi.json").read_text(encoding="utf-8"))

    main_screen = tutorial_ui["main"]["controls"][0]["Control"]["controls"][0]["MainScreen"]
    content = child_map(main_screen)["ContentScreen"]
    content_children = child_map(content)
    assert content_children["Illustration"].get("propagate_alpha") is True
    assert "StartPractice@TutorialScreen.nav_button" in content_children
    assert content_children["PageTitle"]["size"][0] == "62%+0px"
    assert content_children["PageSummary"]["size"][0] == "62%+0px"
    assert content_children["InputHint"]["size"][0] == "43%+0px"

    guide = tutorial_ui["guide_overlay"]
    assert guide.get("propagate_alpha") is True
    guide_children = child_map(guide)
    assert guide_children["Background"].get("keep_ratio") is False
    assert guide_children["Accent"].get("keep_ratio") is False
    assert guide_children["IconFrame"].get("propagate_alpha") is True
    assert child_map(guide_children["IconFrame"])["Icon"].get("keep_ratio") is True
    assert "Cancel@TutorialScreen.nav_button" in guide_children
    assert guide_children["Continue@TutorialScreen.nav_button"]["$label_text"] == "按下任意键继续"
    assert guide_children["Cancel@TutorialScreen.nav_button"]["$label_text"] == "ESC 退出教学"

    control_children = child_map(control_ui["main"]["controls"][0]["Control"])
    setting_children = child_map(setting_ui["main"]["controls"][0]["Control"])
    emoji_children = child_map(emoji_ui["main"])
    assert "TutorialGuide@TutorialScreen.guide_overlay" in control_children
    assert "TutorialGuide@TutorialScreen.guide_overlay" in setting_children
    assert "TutorialGuide@TutorialScreen.guide_overlay" in emoji_children
    focus = control_children["TutorialButtonFocus"]
    assert focus["type"] == "panel" and focus["visible"] is False
    assert focus["layer"] < guide["layer"]
    focus_children = child_map(focus)
    assert focus_children["IdleFill"]["keep_ratio"] is False
    assert focus_children["PressedFill"]["keep_ratio"] is False
    assert all(focus_children[name]["keep_ratio"] is False for name in ("Top", "Bottom", "Left", "Right"))
    for side in ("PromptLeft", "PromptRight", "PromptAbove", "PromptBelow"):
        assert any(name.split("@", 1)[0] == side for name in focus_children)
    prompt_template = control_ui["tutorial_button_prompt"]
    assert prompt_template["type"] == "panel" and prompt_template["visible"] is False
    assert all(child.get("type") != "button" for child in child_map(prompt_template).values())

    catalog = load_catalog()
    basic = next(chapter for chapter in catalog if chapter["id"] == "basic_ui")
    pages = [page for section in basic["sections"] for page in section["pages"]]
    assert len(pages) == 10
    assert "perspective" not in [page["id"] for page in pages]
    for page in pages:
        illustration = page.get("illustration", {})
        practice = page.get("practice", {})
        assert illustration.get("texture"), page["id"]
        assert illustration.get("caption"), page["id"]
        illustration_texture = illustration["texture"]
        assert any(
            (RESOURCE_DIR / (illustration_texture + extension)).is_file()
            for extension in (".png", ".tga")
        ), (page["id"], illustration_texture)
        assert practice.get("surface") in ("Control", "MainSetting"), page["id"]
        assert practice.get("steps"), page["id"]
        for step in practice["steps"]:
            for key in ("title", "instruction", "hint", "action", "success", "retry", "icon"):
                assert step.get(key), (page["id"], key)
            assert any(
                (RESOURCE_DIR / (step["icon"] + extension)).is_file()
                for extension in (".png", ".tga")
            ), (page["id"], step["icon"])

    setting_page = next(page for page in pages if page["id"] == "settings_overview")
    assert setting_page["practice"]["surface"] == "MainSetting"
    assert setting_page["practice"]["close_main_setting"] is False
    assert [step["action"] for step in setting_page["practice"]["steps"]] == [
        "settings_general_control", "settings_detail_skill", "settings_slot", "settings_close"
    ]
    assert all(page["practice"]["close_main_setting"] for page in pages if page is not setting_page)

    auxiliary = next(section for section in basic["sections"] if section["id"] == "auxiliary")
    assert [page["id"] for page in auxiliary["pages"]] == [
        "swap_hand", "back_item", "fight_mode", "emote"
    ]
    fight_page = next(page for page in pages if page["id"] == "fight_mode")
    assert len(fight_page["practice"]["steps"]) == 2
    emote_page = next(page for page in pages if page["id"] == "emote")
    assert emote_page["practice"]["steps"][1]["surface"] == "EmojiUi"

    print("tutorial practical guidance regression: PASS")


if __name__ == "__main__":
    main()
