#!/usr/bin/env python3
"""Focused regression checks for MainSetting current-page fuzzy search."""

from __future__ import print_function

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
MAIN_PATH = ROOT / "src/SwordSoul_NewERA_B/SwordSoulFightScripts/UISystem/MainSetting.py"
CONFIG_PATH = ROOT / "src/SwordSoul_NewERA_B/SwordSoulFightScripts/UISystem/UIConfig.py"
JSON_PATH = ROOT / "src/SwordSoul_NewERA_R/ui/MainSetting.json"


def load_search_helpers(source):
    tree = ast.parse(source)
    selected = []
    for node in tree.body:
        if isinstance(node, ast.Try):
            selected.append(node)
        elif isinstance(node, ast.FunctionDef) and node.name in (
            "NormalizeSettingSearchText",
            "IsSettingSearchMatch",
        ):
            selected.append(node)
    namespace = {}
    module = ast.Module(body=selected, type_ignores=[])
    exec(compile(module, str(MAIN_PATH), "exec"), namespace)
    return namespace["NormalizeSettingSearchText"], namespace["IsSettingSearchMatch"]


def main():
    main_source = MAIN_PATH.read_text(encoding="utf-8")
    config_source = CONFIG_PATH.read_text(encoding="utf-8")
    json_source = JSON_PATH.read_text(encoding="utf-8")

    normalize, matches = load_search_helpers(main_source)
    assert normalize(" 原 生 动 作 ") == "原生动作"
    assert matches("动作", "原生动作优化")
    assert matches("原动优", "原生动作优化")
    assert matches("allowmove", "AllowMoveAttack")
    assert matches("锁目", "自动锁定目标")
    assert not matches("刀光", "原生动作优化", "NativeAnimation")

    for snippet in (
        'SearchScreen = GeneralScreen + "/SearchScreen"',
        'SearchEditBox = SearchScreen + "/search_edit_box"',
        'SearchClearButton = SearchScreen + "/Clear"',
        'SearchButton = SearchScreen + "/Search"',
    ):
        assert snippet in config_source, "missing search UI path: %s" % snippet

    for snippet in (
        '"SearchScreen"',
        '"search_edit_box@common.text_edit_box"',
        '"Search@common.button"',
        '"Clear@common.button"',
    ):
        assert snippet in json_source, "missing user-authored search control: %s" % snippet

    for snippet in (
        "def SetSearchKeyword(self, Keyword, Refresh=False):",
        "def GetRenderConfigs(self):",
        "Config.get(\"search_keywords\", [])",
        "def OnSearch(self, args):",
        "def OnClearSearch(self, args):",
        "GeneralScreenConfig.SearchButton",
        "GeneralScreenConfig.SearchClearButton",
        "SearchEditControl.asTextEditBox().GetEditText()",
        'SearchEditBox.SetEditText(u"")',
        "HadActiveSearch = bool(self.SearchKeyword)",
        "if not HadActiveSearch and not HadInput:",
        "CurrentScreen.render()",
        "self._PrepareScreenSearch(TheScreen)",
    ):
        assert snippet in main_source, "missing search behavior: %s" % snippet

    create_start = main_source.index("    def OnCreate(self):", main_source.index("class GeneralScreenSystem"))
    create_end = main_source.index("\n    def _PrepareScreenSearch", create_start)
    create_source = main_source[create_start:create_end]
    assert create_source.count("GeneralScreenConfig.SearchClearButton") == 1

    print("MainSetting fuzzy search regression: PASS")


if __name__ == "__main__":
    main()
