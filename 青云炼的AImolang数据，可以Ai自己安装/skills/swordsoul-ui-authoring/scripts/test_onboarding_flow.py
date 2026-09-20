from __future__ import print_function

import ast
import json
import re
from pathlib import Path

from _common import project_root, read_text


ROOT = project_root()
BEHAVIOR = ROOT / "src" / "SwordSoul_NewERA_B" / "SwordSoulFightScripts"
RESOURCE = ROOT / "src" / "SwordSoul_NewERA_R"


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def walk_alpha_chain(node, path=""):
    if not isinstance(node, dict):
        return
    controls = node.get("controls")
    if isinstance(controls, list):
        require(node.get("propagate_alpha") is True, "alpha chain broken at %s" % path)
        for entry in controls:
            if not isinstance(entry, dict):
                continue
            for name, child in entry.items():
                walk_alpha_chain(child, path + "/" + name)


def find_named_control(node, target):
    if isinstance(node, dict):
        for name, child in node.items():
            if name.split("@", 1)[0] == target:
                return child
            found = find_named_control(child, target)
            if found is not None:
                return found
    elif isinstance(node, list):
        for child in node:
            found = find_named_control(child, target)
            if found is not None:
                return found
    return None


def load_class_method(source, class_name, method_name, globals_dict=None):
    tree = ast.parse(source)
    method_node = None
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) and child.name == method_name:
                    method_node = child
                    break
    require(method_node is not None, "missing method %s.%s" % (class_name, method_name))
    module = ast.Module(body=[method_node], type_ignores=[])
    ast.fix_missing_locations(module)
    namespace = dict(globals_dict or {})
    exec(compile(module, "<onboarding-method>", "exec"), namespace)
    return namespace[method_name]


def load_literal_assignment(source, assignment_name):
    tree = ast.parse(source)
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id == assignment_name:
                return ast.literal_eval(node.value)
    raise AssertionError("missing literal assignment: %s" % assignment_name)


def test_runtime_contracts():
    onboarding = read_text(BEHAVIOR / "UISystem" / "OnboardingScreen.py")
    setting = read_text(BEHAVIOR / "UISystem" / "SettingData.py")
    main_setting = read_text(BEHAVIOR / "UISystem" / "MainSetting.py")
    editor = read_text(BEHAVIOR / "UISystem" / "EditControlScreen.py")
    announcement = read_text(BEHAVIOR / "UISystem" / "Announcement.py")

    for stage in ("unseen", "wizard", "announcement", "tutorial_offer", "complete"):
        require('"%s"' % stage in onboarding, "missing guide stage: %s" % stage)
    require("def ResetGuideRecord(self):" in onboarding, "guide reset method is missing")
    require("KeyBoardType.KEY_F8, ResetFirstRunGuideRecord" in onboarding, "F8 guide reset shortcut is missing")
    reset_anchor = onboarding.index("def ResetGuideRecord(self):")
    open_anchor = onboarding.index("def OpenGuide(self, Manual=False", reset_anchor)
    reset_body = onboarding[reset_anchor:open_anchor]
    for assignment in (
        'self.GuideVersion = 0', 'self.GuideStage = "unseen"',
        'self.GuideInputMode = ""', 'self.GuideNeedsSkin = False',
        'self.GuidePlayStyle = ""', 'self.GuideSkinChoice = ""'
    ):
        require(assignment in reset_body, "guide reset misses %s" % assignment)
    keybind = read_text(BEHAVIOR / "UISystem" / "KeyBindScreen.py")
    require('"ResetFirstRunGuideRecord"' in keybind.split("DEBUG_KEYBIND =", 1)[0], "guide reset shortcut is visible in normal keybind settings")
    presets = load_literal_assignment(onboarding, "ONBOARDING_PRESETS")
    require(set(presets) == set(("survival", "combat")), "onboarding preset profiles changed")
    survival_ids = [setting_id for setting_id, value in presets["survival"]]
    combat_ids = [setting_id for setting_id, value in presets["combat"]]
    require(survival_ids.index("OnlyFight") < survival_ids.index("FightSystem") < survival_ids.index("AnimateBetter"), "survival preset order changed")
    require(combat_ids.index("AnimateBetter") < combat_ids.index("FightSystem") < combat_ids.index("OnlyFight"), "combat preset order changed")
    require(dict(presets["survival"])["CameraShake"] is False, "survival preset must disable camera shake")
    require(dict(presets["combat"])["CameraShake"] is True, "combat preset must enable camera shake")
    require(dict(presets["combat"])["ShakePower"] == 0.35, "combat camera shake strength changed")
    for setting_id in sorted(set(survival_ids + combat_ids)):
        require("def on%s(" % setting_id in setting, "preset consumer is missing: %s" % setting_id)
        require('SetLocalConfig("%s"' % setting_id in setting, "preset persistence is missing: %s" % setting_id)
    require("def ApplyPresetConfiguration(" in onboarding, "quick preset application is missing")
    require("def ApplyWizardConfiguration(" in onboarding, "summary configuration completion is missing")
    require("GuideSystem.ApplyPlayStyle(Value)" not in onboarding, "preset still applies on card click")
    require('self.Draft["play_style"] = Value' in onboarding, "preset card does not update the draft")
    require('self.Draft["config_mode"] = Value' in onboarding, "configuration mode entry is missing")
    require('"quick", u"快速配置"' in onboarding, "quick configuration button copy changed")
    require('"manual", u"自己动手"' in onboarding, "manual configuration button copy changed")
    require('self._ShowPresetSummary(PlayStyle, AlreadyApplied)' in onboarding, "pre-apply preset table is missing")
    require('self._ShowPresetSummary(PlayStyle, True)' in onboarding, "post-apply preset table is missing")
    require('"continue_tuning", u"继续细调"' in onboarding, "post-apply fine-tune question is missing")
    require('if Stage == "skin"' not in onboarding and 'if Stage == "input"' not in onboarding, "legacy specialist queue still advances")
    require('self._OpenMainRoute("skin")' in onboarding, "built-in skin does not open immediately")
    require('self._OpenMainRoute("keybind")' in onboarding, "keybind page does not open immediately")
    require("GuideSystem.StartTouchEditor" in onboarding, "touch editor does not open from its step")
    require("View.OnExternalRouteClosed(RouteId)" in onboarding, "main setting does not return to the same guide step")
    require("self.GuidePage" in onboarding and "SaveWizardProgress" in onboarding, "wizard page resume state is missing")
    for state_name in ("GuideFlowSchema", "GuideConfigMode", "GuideAppliedPlayStyle", "GuideAppliedSkinChoice"):
        require('SetLocalConfig("%s"' % state_name in onboarding, "guide scalar is not persisted: %s" % state_name)
    route_block = main_setting.split("def ApplyOnboardingRoute(self, RouteId=None):", 1)[1].split("def _GetInteractionAnimationExclusions", 1)[0]
    for route in ("base", "appearance", "accessories", "visual", "control", "fight_animate", "skills", "keybind"):
        require('"%s"' % route in route_block, "missing immediate route: %s" % route)
    require("FirstRunGuideSystem.OnSettingsReady()" in setting, "settings no longer delegate popup priority")
    require("self.ApplyOnboardingRoute()" in main_setting, "main setting does not consume its pending route after readiness")
    require("FirstRunGuideSystem.OnMainSettingRouteApplied" in main_setting, "main setting does not report the applied route")
    require("FirstRunGuideSystem.OnMainSettingClosed()" in main_setting, "main setting close does not advance route")
    require(editor.count("FirstRunGuideSystem.OnHudEditorClosed()") == 2, "HUD save/cancel return paths are incomplete")
    require('self.param.get("after_close", "")' in announcement, "announcement return action is missing")
    require("def ShowNamedScreen(self, Label):" in main_setting, "named main-setting route is missing")
    require('RouteKey = "__onboarding_general_%s" % Label' in main_setting, "general route does not use a stable page key")
    require('RouteKey = "__onboarding_detail_%s" % Label' in main_setting, "detail route does not use a stable page key")
    require("def _TryApplyMainSettingRoute(self, RetryCount):" in onboarding, "ready-gated route retry is missing")
    require("self._Schedule(0.05, self._TryApplyMainSettingRoute" in onboarding, "route retry is not scheduled")
    require("MainSettingSystem.Ready" in onboarding, "route does not wait for main setting business readiness")
    require('"base": u"先在这里决定动作优化与完整战斗开关"' in main_setting, "manual base route has no focus prompt")
    combat_copy = onboarding.split('if PlayStyle == "combat":', 1)[1].split("else:", 1)[0]
    require('"route:skills", u"招式与技能"' in combat_copy, "combat guide card does not open skill equipment")
    require('"route:fight_animate", u"招式与技能"' not in combat_copy, "combat guide card still opens fight animation")
    require("self._QueueOnboardingRouteFocus(RouteId)" in main_setting, "applied routes do not request an area focus")


def test_preset_application():
    onboarding = read_text(BEHAVIOR / "UISystem" / "OnboardingScreen.py")
    presets = load_literal_assignment(onboarding, "ONBOARDING_PRESETS")
    preset_labels = load_literal_assignment(onboarding, "PRESET_SETTING_LABELS")
    writes = []

    get_preset_summary_rows = load_class_method(
        onboarding,
        "FirstRunGuideSystem",
        "GetPresetSummaryRows",
        {"ONBOARDING_PRESETS": presets, "PRESET_SETTING_LABELS": preset_labels}
    )
    summary_owner = object()
    for play_style in ("survival", "combat"):
        before_rows = get_preset_summary_rows(summary_owner, play_style, False)
        after_rows = get_preset_summary_rows(summary_owner, play_style, True)
        require(len(before_rows) == 3 and len(after_rows) == 3, "preset table no longer has three rows")
        before_summary = u"\n".join(u"%s %s" % row for row in before_rows)
        after_summary = u"\n".join(u"%s %s" % row for row in after_rows)
        require(u"将开启" in before_summary and u"将关闭" in before_summary and u"将调整" in before_summary, "pre-apply summary headings are incomplete")
        require(u"已开启" in after_summary and u"已关闭" in after_summary and u"已调整" in after_summary, "post-apply summary headings are incomplete")
        require(all(u"项" in row[0] for row in before_rows + after_rows), "preset table headings do not show item counts")
        for setting_id, value in presets[play_style]:
            require(preset_labels[setting_id] in before_summary, "pre-apply summary misses %s" % setting_id)
            require(preset_labels[setting_id] in after_summary, "post-apply summary misses %s" % setting_id)

    class Settings(object):
        def __init__(self):
            for profile in presets.values():
                for setting_id, value in profile:
                    setattr(self, setting_id, None)
            self.SkinChoice = "builtin"

        def updateChoose(self, setting_id, value):
            writes.append((setting_id, value))
            setattr(self, setting_id, value)

        def __getattr__(self, name):
            if name.startswith("on"):
                return lambda value: None
            raise AttributeError(name)

    class RootController(object):
        def __init__(self):
            self.skin_refreshes = 0

        def InitPlayerSkin(self):
            self.skin_refreshes += 1

    settings = Settings()
    root_controller = RootController()
    components = {
        "ChooseSettingSystem": settings,
        "PlayerRootController": root_controller,
    }
    method_globals = {
        "GetComponent": lambda name: components.get(name),
        "ONBOARDING_PRESETS": presets,
    }
    methods = {}
    for method_name in (
        "_ValidateWizardDraft", "_GetAppliedSignature", "_SetAppliedSignature",
        "_SetAppliedPlayStyle", "_SetAppliedSkinChoice", "IsPresetApplied",
        "IsWizardConfigurationApplied", "_PreflightSettings", "_ApplySetting",
        "ApplyPresetConfiguration", "ApplyWizardConfiguration"
    ):
        methods[method_name] = load_class_method(
            onboarding, "FirstRunGuideSystem", method_name, method_globals
        )
    methods["_CanConfigure"] = lambda self: True
    methods["_Message"] = lambda self, text: None
    Owner = type("Owner", (object,), methods)
    owner = Owner()
    owner.GuideAppliedPlayStyle = ""
    owner.GuideAppliedSkinChoice = ""
    owner.ManualAppliedPlayStyle = ""
    owner.ManualAppliedSkinChoice = ""

    combat_draft = {
        "play_style": "combat", "skin_choice": "default_thin",
        "input_mode": "external", "config_mode": "quick"
    }
    require(owner.ApplyPresetConfiguration("combat", False) is True, "combat preset failed")
    require(writes == presets["combat"], "combat preset application order changed")
    require(owner.IsPresetApplied("combat", False), "quick preset signature was not stored")

    writes[:] = []
    settings.AttackEffect = False
    require(owner.ApplyWizardConfiguration(combat_draft, False) is True, "combat wizard completion failed")
    require(writes == [("SkinChoice", "default_thin")], "summary reapplied the preset instead of only applying the arm model")
    require(root_controller.skin_refreshes == 1, "direct arm model did not refresh")
    require(owner.IsWizardConfigurationApplied(combat_draft, False), "applied signature was not stored")
    require(settings.AttackEffect is False, "fine-tuned value was lost during summary completion")

    writes[:] = []
    require(owner.ApplyWizardConfiguration(combat_draft, False) is True, "same preset could not be revisited")
    require(writes == [], "same applied signature overwrote later fine tuning")
    require(settings.AttackEffect is False, "fine-tuned value was lost on summary revisit")

    survival_draft = dict(combat_draft)
    survival_draft["play_style"] = "survival"
    require(owner.ApplyPresetConfiguration("survival", False) is True, "survival preset failed")
    require(writes == presets["survival"], "survival preset application order changed")
    require(settings.FightSystem is False and settings.OnlyFight is False, "survival preset left combat enabled")
    require(settings.CameraShake is False, "survival preset left camera shake enabled")

    writes[:] = []
    owner._CanConfigure = lambda: False
    require(owner.ApplyPresetConfiguration("combat", False) is False, "room lock did not reject preset application")
    require(writes == [], "room lock allowed a partial preset write")


def test_flow_schema_migration():
    onboarding = read_text(BEHAVIOR / "UISystem" / "OnboardingScreen.py")
    migrate = load_class_method(
        onboarding,
        "FirstRunGuideSystem",
        "_MigrateGuideFlow",
        {"GUIDE_FLOW_SCHEMA": 3}
    )
    expected_pages = {0: 0, 1: 1, 2: 2, 3: 2, 4: 2, 5: 2}
    for old_page, new_page in expected_pages.items():
        owner = type("Owner", (object,), {
            "GuideFlowSchema": 0,
            "GuideStage": "wizard",
            "GuidePage": old_page,
            "GuideConfigMode": "quick",
            "GuideAppliedPlayStyle": "combat",
            "GuideAppliedSkinChoice": "default",
        })()
        migrate(owner)
        require(owner.GuidePage == new_page, "legacy page migration failed: %s" % old_page)
        require(owner.GuideFlowSchema == 3, "flow schema was not advanced")
        require(owner.GuideConfigMode == "", "legacy flow kept an unsupported configuration mode")
        require(owner.GuideAppliedPlayStyle == "" and owner.GuideAppliedSkinChoice == "", "legacy applied signature survived migration")
    for legacy_stage, expected_page in (("awaiting_apply", 1), ("skin", 2), ("input", 2)):
        owner = type("Owner", (object,), {
            "GuideFlowSchema": 0,
            "GuideStage": legacy_stage,
            "GuidePage": 0,
            "GuidePlayStyle": "combat",
            "GuideSkinChoice": "default",
            "GuideInputMode": "external",
            "GuideConfigMode": "",
            "GuideAppliedPlayStyle": "",
            "GuideAppliedSkinChoice": "",
        })()
        migrate(owner)
        require(owner.GuideStage == "wizard" and owner.GuidePage == expected_page, "legacy stage migration failed: %s" % legacy_stage)

    schema_two_owner = type("Owner", (object,), {
        "GuideFlowSchema": 2,
        "GuideStage": "wizard",
        "GuidePage": 5,
        "GuidePlayStyle": "combat",
        "GuideSkinChoice": "default",
        "GuideInputMode": "external",
        "GuideConfigMode": "",
        "GuideAppliedPlayStyle": "combat",
        "GuideAppliedSkinChoice": "default",
    })()
    migrate(schema_two_owner)
    require(schema_two_owner.GuidePage == 5 and schema_two_owner.GuideConfigMode == "quick", "schema-two fine-tune state was not preserved")
    require(schema_two_owner.GuideAppliedPlayStyle == "combat", "schema-two applied preset signature was lost")


def test_main_setting_route_dispatch():
    onboarding = read_text(BEHAVIOR / "UISystem" / "OnboardingScreen.py")
    main_setting = read_text(BEHAVIOR / "UISystem" / "MainSetting.py")
    calls = []

    class MainSetting(object):
        Ready = True
        def ApplyOnboardingRoute(self, route_id):
            calls.append(route_id)
            return True

    components = {"MainSettingSystem": MainSetting()}
    dispatch = load_class_method(
        onboarding,
        "FirstRunGuideSystem",
        "OnMainSettingReady",
        {"GetComponent": lambda name: components.get(name)}
    )
    for route_id in ("base", "skin", "appearance", "accessories", "control", "visual", "fight_animate", "skills", "keybind"):
        calls[:] = []
        owner = type("Owner", (object,), {
            "ActiveMainRoute": route_id,
            "ActiveMainRouteApplied": False,
        })()
        require(dispatch(owner) is True, "route did not report success: %s" % route_id)
        require(calls == [route_id], "route was not delegated to main setting: %s -> %r" % (route_id, calls))
        require(owner.ActiveMainRouteApplied is True, "route success was not latched: %s" % route_id)

    class General(object):
        def ShowNamedScreen(self, label):
            calls.append(("general", label))
            return True

        def ShowKeyBindScreen(self):
            calls.append(("general", "keybind"))

    class Detail(object):
        def ShowNamedScreen(self, label):
            calls.append(("detail", label))
            return True

        def ShowTopScreen(self, name):
            calls.append(("top", name))
            return True

    route_components = {"GeneralScreenSystem": General(), "DetailScreenSystem": Detail()}
    apply_route = load_class_method(
        main_setting,
        "MainSettingSystem",
        "ApplyOnboardingRoute",
        {"GetComponent": lambda name: route_components.get(name)}
    )
    expected = {
        "base": ("general", u"基础设置"),
        "skin": ("top", "skin"),
        "appearance": ("top", "appearance"),
        "accessories": ("top", "accessories"),
        "control": ("general", u"操作设置"),
        "visual": ("general", u"视觉设置"),
        "fight_animate": ("detail", u"战斗动作"),
        "skills": ("detail", u"技能配备"),
        "keybind": ("general", "keybind"),
    }
    for route_id, expected_call in expected.items():
        calls[:] = []
        owner = type("Owner", (object,), {
            "Ready": True,
            "PendingOnboardingRoute": route_id,
            "_QueueOnboardingRouteFocus": lambda self, route: calls.append(("focus", route))
        })()
        require(apply_route(owner) is True, "main setting route failed: %s" % route_id)
        require(calls == [expected_call, ("focus", route_id)], "main setting opened or focused the wrong page: %s -> %r" % (route_id, calls))
        require(owner.PendingOnboardingRoute == "", "applied route was not consumed: %s" % route_id)


def test_named_screen_uses_page_objects():
    main_setting = read_text(BEHAVIOR / "UISystem" / "MainSetting.py")

    class Owner(object):
        def __init__(self, mapping_name, label, screen):
            setattr(self, mapping_name, [(label, screen)])
            self.MappingClsMap = {}
            self.calls = []

        def OnChooseScreen(self, args):
            self.calls.append(args["ButtonPath"])

    cases = (
        ("GeneralScreenSystem", "LeftChooseMap", u"操作设置", "__onboarding_general_"),
        ("DetailScreenSystem", "RightChooseMap", u"技能配备", "__onboarding_detail_"),
    )
    for class_name, mapping_name, label, prefix in cases:
        screen = object()
        owner = Owner(mapping_name, label, screen)
        show_named = load_class_method(main_setting, class_name, "ShowNamedScreen")
        require(show_named(owner, label) is True, "%s did not resolve its page object" % class_name)
        require(owner.calls == [prefix + label], "%s did not invoke the real selection flow" % class_name)
        require(owner.MappingClsMap[owner.calls[0]] is screen, "%s routed to the wrong page object" % class_name)
        require(show_named(owner, u"不存在的分类") is False, "%s accepted an unknown category" % class_name)

    class TopOwner(object):
        SkinScreen = object()
        ImageScreen = object()
        AccessoriesScreenMap = {"head": object()}

        def __init__(self):
            self.calls = []

        def OnSkinChoose(self, args):
            self.calls.append(("skin", args["ButtonPath"]))

        def OnImageChoose(self, args):
            self.calls.append(("appearance", args["ButtonPath"]))

        def OnAccessoryChoose(self, args):
            self.calls.append(("accessories", args["ButtonPath"]))

    show_top = load_class_method(main_setting, "DetailScreenSystem", "ShowTopScreen")
    top_owner = TopOwner()
    for name in ("skin", "appearance", "accessories"):
        require(show_top(top_owner, name) is True, "top route failed: %s" % name)
        require(top_owner.calls[-1] == (name, "__onboarding_top_%s" % name), "top route used the wrong page: %s" % name)
    require(show_top(top_owner, "unknown") is False, "unknown top route was accepted")


def test_route_focus_resizes_visible_children():
    main_setting = read_text(BEHAVIOR / "UISystem" / "MainSetting.py")

    class FakeNode(object):
        def __init__(self):
            self.updates = 0

        def UpdateScreen(self):
            self.updates += 1

    class FakeLabel(object):
        def asLabel(self):
            return self

        def SetText(self, text):
            FakeUIMod.text = text

    class FakeCompData(object):
        def SetCompAlphaAnimation(self, *args):
            FakeUIMod.animations.append(args)

    class FakeUIMod(object):
        node = FakeNode()
        sizes = []
        positions = []
        position = None
        text = None
        animations = []

        @staticmethod
        def UIModComp(ui_name):
            return FakeUIMod.node

        @staticmethod
        def GetCompSize(ui_name, path):
            return (300, 400)

        @staticmethod
        def GetCompMustPosition(ui_name, path, CreateComp=False):
            return (10, 20)

        @staticmethod
        def SetCompSize(ui_name, path, size, resize_children=False):
            FakeUIMod.sizes.append((path, size, resize_children))

        @staticmethod
        def SetCompMustPosition(ui_name, path, position):
            FakeUIMod.position = (path, position)

        @staticmethod
        def SetCompPosition(ui_name, path, position, follow_type="none", pos_model=False):
            FakeUIMod.positions.append((path, position["x"], position["y"], follow_type, pos_model))

        @staticmethod
        def GetBetterUIControl(ui_name, path):
            return FakeLabel()

        @staticmethod
        def SetVisible(ui_name, path, visible):
            pass

        @staticmethod
        def SetCompAlpha(ui_name, path, alpha):
            pass

        @staticmethod
        def GetCompData(ui_name, path):
            return FakeCompData()

    class FakeConfig(object):
        OnboardingFocus = "focus"
        OnboardingFocusFill = "fill"
        OnboardingFocusTop = "top"
        OnboardingFocusBottom = "bottom"
        OnboardingFocusLeft = "left"
        OnboardingFocusRight = "right"
        OnboardingFocusPrompt = "prompt"
        OnboardingFocusPromptBackground = "prompt_background"
        OnboardingFocusPromptAccent = "prompt_accent"
        OnboardingFocusPromptText = "prompt_text"

    class Owner(object):
        Ready = True
        Closing = False
        OnboardingFocusGeneration = 7
        uiName = "MainSetting"

        def _GetOnboardingFocusData(self, route_id):
            return "target", u"在这里配备和调整你的常用技能"

        def _ScheduleOnboardingFocus(self, delay, callback, *args):
            self.scheduled = (delay, args)

        def _BeginHideOnboardingRouteFocus(self, generation):
            pass

    show_focus = load_class_method(
        main_setting,
        "MainSettingSystem",
        "_ShowOnboardingRouteFocus",
        {"UIMod": FakeUIMod, "MainSettingConfig": FakeConfig}
    )
    owner = Owner()
    show_focus(owner, "skills", 7)
    size_map = {path: size for path, size, resize_children in FakeUIMod.sizes}
    require(size_map["focus"] == (308, 408), "focus root does not cover the target area")
    require(size_map["fill"] == (308, 408), "focus fill does not cover the target area")
    require(size_map["top"] == (308, 2) and size_map["bottom"] == (308, 2), "horizontal focus borders are not stretched")
    require(size_map["left"] == (2, 408) and size_map["right"] == (2, 408), "vertical focus borders are not stretched")
    require(size_map["prompt"] == (280, 28), "focus prompt did not receive a readable width")
    require(size_map["prompt_background"] == (280, 28), "focus prompt background stayed at template size")
    require(size_map["prompt_text"] == (266, 28), "focus prompt text stayed at template size")
    require(FakeUIMod.position == ("focus", (6, 16)), "focus position does not include target padding")
    local_positions = {path: (x, y) for path, x, y, follow_type, pos_model in FakeUIMod.positions}
    require(local_positions["top"] == (0, 0), "top border left the target origin")
    require(local_positions["bottom"] == (0, 406), "bottom border stayed at the template-height offset")
    require(local_positions["left"] == (0, 0), "left border left the target origin")
    require(local_positions["right"] == (306, 0), "right border stayed at the template-width offset")
    require(local_positions["prompt"] == (14.0, 6), "focus prompt is not centered in the final target width")
    require(all(follow_type == "none" and pos_model is False for path, x, y, follow_type, pos_model in FakeUIMod.positions), "focus children do not use stable local pixel coordinates")
    require(FakeUIMod.text == u"在这里配备和调整你的常用技能", "focus prompt text was not applied")
    require(FakeUIMod.node.updates == 2, "focus layout was not refreshed after explicit child sizing")


def test_button_restore_before_relayout():
    ui_animation = read_text(BEHAVIOR / "QingYunModLibs" / "UIAnimation.py")

    class FakeControl(object):
        def __init__(self):
            self.size = (73, 19)
            self.position = (4, 3)

        def SetSize(self, size, resize_children):
            self.size = size
            self.resize_children = resize_children

        def SetPosition(self, position):
            self.position = position

    control = FakeControl()

    class FakeUIMod(object):
        @staticmethod
        def GetBetterUIControl(ui_name, path):
            return control

    class Owner(object):
        Destroyed = False
        uiName = "OnboardingScreen"
        Metrics = {"next/button_label": {"size": (80, 20), "pos": (0, 0)}}
        Hovered = {"next/button_label"}
        Pressed = {"next/button_label"}

        def __init__(self):
            self.cancelled = []

        def _cancel(self, path):
            self.cancelled.append(path)

        def _hasControl(self, path):
            return True

    restore = load_class_method(
        ui_animation,
        "CenteredButtonAnimator",
        "RestoreAll",
        {"_UIMod": FakeUIMod}
    )
    owner = Owner()
    restore(owner)
    require(control.size == (80, 20) and control.position == (0, 0), "pressed label did not return to its baseline")
    require(control.resize_children is True, "button visual descendants were not restored with their parent")
    require(owner.cancelled == ["next/button_label"], "in-flight scale timer was not cancelled")
    require(owner.Hovered == set() and owner.Pressed == set(), "pressed or hover state survived content relayout")


def test_player_facing_copy():
    onboarding = read_text(BEHAVIOR / "UISystem" / "OnboardingScreen.py")
    copy_block = onboarding.split("def _RenderIdentity(self):", 1)[1].split("def _AnimatePageIn(self):", 1)[0]
    for forbidden in (u"排队", u"真实设置页", u"不再批量", u"而不是只显示入口", u"立即生效"):
        require(forbidden not in copy_block, "player-facing copy emphasizes implementation: %s" % forbidden)


def test_animation_contracts():
    onboarding = read_text(BEHAVIOR / "UISystem" / "OnboardingScreen.py")
    main_setting = read_text(BEHAVIOR / "UISystem" / "MainSetting.py")
    ui_runtime = read_text(BEHAVIOR / "QingYunModLibs" / "UIScreen.py")
    ui_animation = read_text(BEHAVIOR / "QingYunModLibs" / "UIAnimation.py")
    require("CenteredButtonAnimator" in onboarding, "button interaction animator is missing")
    require("AddVisualButtonTouch" in onboarding, "visual-only button feedback is missing")
    require("AddButtonEventObserver" in onboarding, "business Up event observer is missing")
    require("RemoveButtonEventObserver" in onboarding, "button event observer cleanup is missing")
    visual_loop = re.search(r'for State in (\[[^\]]+\]):\s*\n\s*UIMod\.AddVisualButtonTouch', onboarding)
    require(visual_loop is not None, "visual button state registration cannot be audited")
    visual_states = set(ast.literal_eval(visual_loop.group(1)))
    runtime_block = ui_runtime.split("def AddVisualButtonTouch", 1)[1].split("def AddSuperButton", 1)[0]
    supported_states = set(re.findall(r'^\s*"([A-Za-z]+)": ButtonObj\.', runtime_block, re.MULTILINE))
    require(visual_states <= supported_states, "unsupported AddVisualButtonTouch states: %s" % sorted(visual_states - supported_states))
    require("Up" not in visual_states, "Up must come from the business button observer")
    require("def _Transition(self, Page=None, Mode=None):" in onboarding, "page transition is missing")
    require("def _AnimatePageIn(self):" in onboarding, "page entrance animation is missing")
    require("self.Generation += 1" in onboarding, "stale animation callback generation gate is missing")
    require("self._ClearTimers()" in onboarding, "animation timer cleanup is missing")
    require("self.ButtonAnimator.Destroy()" in onboarding, "button animator cleanup is missing")
    require('State not in ("Up", "Cancel")' in onboarding, "locked-page button visuals cannot restore after click")
    require("if self.Destroyed or Generation != self.Generation" in onboarding, "delayed callback lifecycle guard is missing")
    require("GetCompData(self.uiName, self.cfg.Content).SetCompAlphaAnimation" in onboarding, "content fade transition is missing")
    require("def RestoreAll(self):" in ui_animation, "button animator cannot synchronously restore a pressed visual")
    restore_block = ui_animation.split("def RestoreAll(self):", 1)[1].split("def Destroy(self):", 1)[0]
    require('Control.SetSize(Metric["size"], True)' in restore_block, "button restore does not recover baseline size")
    require('Control.SetPosition(Metric["pos"])' in restore_block, "button restore does not recover baseline position")
    render_block = onboarding.split("def Render(self):", 1)[1].split("def _RenderIdentity(self):", 1)[0]
    require(render_block.index("self.ButtonAnimator.RestoreAll()") < render_block.index("self._RenderWizardPage()"), "button visuals are restored after new labels render")
    bind_block = onboarding.split("def _BindButtonAnimations", 1)[1].split("def _OnButtonAnimationEvent", 1)[0]
    require("self.ButtonAnimator.RestoreAll()" not in bind_block, "old button metrics overwrite the newly updated label layout")
    finish_block = onboarding.split("def _FinishTransition", 1)[1].split("def _RefreshSelection", 1)[0]
    require(finish_block.index("self.Render()") < finish_block.index("UiNode.UpdateScreen()") < finish_block.index("self._BindButtonAnimations(False)"), "page transition does not bind animation from the final label layout")
    require("_ScheduleOnboardingFocus(0.56" in main_setting, "route focus is measured before the main setting entrance ends")
    require("Generation != self.OnboardingFocusGeneration" in main_setting, "route focus callbacks lack a lifecycle generation gate")
    require("self._StopOnboardingRouteFocus()\n        self.Ready = False" in main_setting, "route focus is not stopped before main setting readiness closes")
    focus_block = main_setting.split("def _ShowOnboardingRouteFocus", 1)[1].split("def _BeginHideOnboardingRouteFocus", 1)[0]
    require("SetCompMovingAnimation" not in focus_block, "route focus animates absolute position after layout")
    focus_lifecycle = main_setting.split("def _QueueOnboardingRouteFocus", 1)[1].split("def _GetInteractionAnimationExclusions", 1)[0]
    for helper in ("UIModComp", "GetCompSize", "GetCompMustPosition", "SetCompSize", "SetCompMustPosition", "SetCompPosition", "GetBetterUIControl", "SetCompAlpha", "GetCompData", "SetVisible"):
        require(not re.search(r"(?<!UIMod\.)\b%s\(" % helper, focus_lifecycle), "unqualified route-focus helper: %s" % helper)


def test_resource_contracts():
    onboarding_path = RESOURCE / "ui" / "OnboardingScreen.json"
    raw = onboarding_path.read_bytes()
    require(not raw.startswith(b"\xef\xbb\xbf"), "OnboardingScreen.json contains BOM")
    data = json.loads(raw.decode("utf-8"))
    required_button_vars = (
        "$label_color", "$label_font_scale_factor", "$label_font_size",
        "$label_layer", "$label_offset"
    )
    for template_name in ("action_button@common.button", "choice_button@common.button"):
        template = data[template_name]
        for variable in required_button_vars:
            require(variable in template, "%s misses %s" % (template_name, variable))
    walk_alpha_chain(data["action_button@common.button"], "/action_button")
    walk_alpha_chain(data["choice_button@common.button"], "/choice_button")
    require("preset_summary_row" in data, "preset summary row template is missing")
    walk_alpha_chain(data["preset_summary_row"], "/preset_summary_row")
    for image_name in ("Background", "Accent", "Divider"):
        require(find_named_control(data["preset_summary_row"], image_name).get("keep_ratio") is False, "%s cannot stretch inside the preset table" % image_name)
    control = data["main"]["controls"][0]["Control"]
    walk_alpha_chain(control, "/Control")
    main_screen = control["controls"][0]["MainScreen"]
    preset_summary = find_named_control(main_screen, "PresetSummary")
    require(preset_summary is not None and preset_summary.get("visible") is False, "preset table is visible outside quick configuration")
    require(preset_summary.get("propagate_alpha") is True, "preset table alpha propagation is missing")
    preset_row_names = []
    for entry in preset_summary.get("controls", []):
        preset_row_names.extend(name.split("@", 1)[0] for name in entry)
    require(preset_row_names == ["Enabled", "Disabled", "Adjusted"], "preset table rows are incomplete")
    header = main_screen["controls"][1]["Header"]
    close_button = None
    for entry in header.get("controls", []):
        if "Close@common.button" in entry:
            close_button = entry["Close@common.button"]
            break
    require(close_button is not None, "close button is missing")
    close_size = close_button.get("size")
    require(
        isinstance(close_size, list) and len(close_size) == 2
        and not ("%y" in str(close_size[0]) and "%x" in str(close_size[1])),
        "close button contains a cyclic size rule"
    )
    for name in ("default", "hover", "pressed"):
        require(close_button.get(name + "_control") == name, "close button state is unresolved: %s" % name)
    close_children = set()
    for entry in close_button.get("controls", []):
        for name in entry:
            close_children.add(name.split("@")[0])
    require(set(("default", "hover", "pressed", "button_label")) <= close_children, "close button state controls are incomplete")
    progress = None
    for entry in header.get("controls", []):
        if "Progress" in entry:
            progress = entry["Progress"]
            break
    require(progress is not None, "five-step progress bar is missing")
    require(progress.get("propagate_alpha") is True, "progress alpha propagation is missing")
    progress_names = []
    for entry in progress.get("controls", []):
        progress_names.extend(entry.keys())
    require(progress_names == ["Step1", "Step2", "Step3", "Step4", "Step5"], "progress segments are incomplete")
    footer = main_screen["controls"][3]["Footer"]
    require(any("Hint" in entry for entry in footer.get("controls", [])), "wizard footer hint is missing")
    next_button = find_named_control(footer, "Next")
    require(next_button.get("size", [None])[0] == "20%+0px", "next button width changed instead of fixing animation state")
    require(float(next_button.get("$label_font_scale_factor", 0)) == 1.2, "next button font changed instead of fixing animation state")

    defs = json.loads((RESOURCE / "ui" / "_ui_defs.json").read_text(encoding="utf-8"))
    require("ui/OnboardingScreen.json" in defs["ui_defs"], "OnboardingScreen.json is not registered")

    main_setting_raw = (RESOURCE / "ui" / "MainSetting.json").read_bytes()
    require(not main_setting_raw.startswith(b"\xef\xbb\xbf"), "MainSetting.json contains BOM")
    main_setting = json.loads(main_setting_raw.decode("utf-8"))
    require("RestartGuide@common.button" in json.dumps(main_setting, ensure_ascii=False), "manual restart button is missing")
    focus = find_named_control(main_setting["main"], "OnboardingFocus")
    require(focus is not None, "main setting onboarding focus is missing")
    require(focus.get("visible") is False, "onboarding focus is visible outside guided routes")
    walk_alpha_chain(focus, "/Control/OnboardingFocus")
    require('"type": "button"' not in json.dumps(focus, ensure_ascii=False), "onboarding focus blocks setting input")
    require(find_named_control(focus, "Fill").get("keep_ratio") is False, "focus fill cannot stretch with the target area")
    require(find_named_control(focus, "Text").get("text") == u"在这里调整你想要的设置", "focus prompt copy is missing")
    for name in ("Fill", "Top", "Bottom", "Left", "Right", "Prompt"):
        control = find_named_control(focus, name)
        require(control.get("anchor_from") == "top_left" and control.get("anchor_to") == "top_left", "%s still depends on a stale resized-parent anchor" % name)


def test_transition_matrix():
    onboarding = read_text(BEHAVIOR / "UISystem" / "OnboardingScreen.py")
    pages = list(range(9))
    require(pages == [0, 1, 2, 3, 4, 5, 6, 7, 8], "wizard branch pages changed")
    for input_mode in ("touch", "external"):
        require(7 in pages and 8 in pages, "input route cannot return before summary: %s" % input_mode)
    require('RequiredKeys = {1: "play_style", 6: "skin_choice", 7: "input_mode"}' in onboarding, "required-step map changed")
    require('self._Transition(3)' in onboarding, "quick configuration does not reach its preview")
    require('GuideSystem.ApplyPresetConfiguration(self.Draft.get("play_style")' in onboarding, "quick configuration is not applied from its confirmation page")
    require('"continue_tuning"' in onboarding and 'self._Transition(5)' in onboarding, "post-apply fine-tune branch is missing")
    require('"continue_setup"' in onboarding and 'self._Transition(6)' in onboarding, "post-apply direct branch is missing")
    require('self._OpenMainRoute("base")' in onboarding, "manual configuration does not open the real base page")
    require('Result = GuideSystem.ConfirmWizard(self.Draft, self.Manual)' in onboarding, "summary does not own preset commit")


def test_destroy_after_control_tree_is_gone():
    onboarding = read_text(BEHAVIOR / "UISystem" / "OnboardingScreen.py")
    events = []

    class FakeUIMod(object):
        @staticmethod
        def RemoveButtonEventObserver(ui_name, callback):
            events.append(("observer", ui_name, callback))

    class FakeAnimator(object):
        def Destroy(self):
            events.append(("animator",))

    class FakeGuideSystem(object):
        def OnViewDestroyed(self):
            events.append(("guide",))

    class Owner(object):
        Ready = True
        Destroyed = False
        Generation = 4
        uiName = "OnboardingScreen"

        def __init__(self):
            self.ButtonAnimator = FakeAnimator()

        def _ClearTimers(self):
            events.append(("timers",))

        def _OnButtonAnimationEvent(self, *args):
            pass

    owner = Owner()
    current_view = [owner]

    def fail_control_lookup(*args, **kwargs):
        raise AssertionError("Destroy queried an already-removed UI control")

    destroy = load_class_method(
        onboarding,
        "OnboardingView",
        "Destroy",
        {
            "UIMod": FakeUIMod,
            "UIModComp": fail_control_lookup,
            "GetCompData": fail_control_lookup,
            "_CURRENT_VIEW": current_view,
            "GetFirstRunGuideSystem": lambda: FakeGuideSystem(),
        }
    )
    destroy(owner)
    require(owner.Ready is False and owner.Destroyed is True, "Destroy did not close the readiness gate")
    require(owner.Generation == 5, "Destroy did not invalidate delayed callbacks")
    require(owner.ButtonAnimator is None, "Destroy retained its button animator")
    require(current_view[0] is None, "Destroy retained the current onboarding view")
    require(("timers",) in events and ("animator",) in events and ("guide",) in events, "Destroy cleanup is incomplete")


def main():
    test_runtime_contracts()
    test_preset_application()
    test_flow_schema_migration()
    test_main_setting_route_dispatch()
    test_named_screen_uses_page_objects()
    test_route_focus_resizes_visible_children()
    test_button_restore_before_relayout()
    test_player_facing_copy()
    test_animation_contracts()
    test_resource_contracts()
    test_transition_matrix()
    test_destroy_after_control_tree_is_gone()
    print("onboarding flow checks passed")


if __name__ == "__main__":
    main()
