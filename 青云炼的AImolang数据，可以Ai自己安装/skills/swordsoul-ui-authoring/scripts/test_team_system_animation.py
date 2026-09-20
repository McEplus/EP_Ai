# coding=utf-8
"""Static regression checks for TeamSystem animation lifecycle and JSON alpha propagation."""
from __future__ import print_function

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
PY_PATH = ROOT / "src/SwordSoul_NewERA_B/SwordSoulFightScripts/UISystem/TeamSystem.py"
ANIMATION_PATH = ROOT / "src/SwordSoul_NewERA_B/SwordSoulFightScripts/QingYunModLibs/UIAnimation.py"
JSON_PATH = ROOT / "src/SwordSoul_NewERA_R/ui/TeamSystem.json"
SERVER_PATH = ROOT / "src/SwordSoul_NewERA_B/SwordSoulFightScripts/TeamSystem/Server.py"


def method_body(source, name, next_name):
    start = source.index("    def %s(" % name)
    end = source.index("    def %s(" % next_name, start)
    return source[start:end]


def assert_alpha_chain(node, path):
    if not isinstance(node, dict):
        return
    controls = node.get("controls")
    if controls is not None:
        assert node.get("propagate_alpha") is True, "alpha propagation break: %s" % path
        for item in controls:
            for name, child in item.items():
                assert_alpha_chain(child, path + "/" + name)


def control_children(node):
    result = {}
    for item in node.get("controls", []):
        result.update(item)
    return result


def find_named_controls(node, target):
    result = []
    if isinstance(node, dict):
        for name, child in node.items():
            if name == target:
                result.append(child)
            result.extend(find_named_controls(child, target))
    elif isinstance(node, list):
        for child in node:
            result.extend(find_named_controls(child, target))
    return result


def assert_center_anchor(node, path):
    assert node.get("anchor_from") == "center", "center anchor_from missing: %s" % path
    assert node.get("anchor_to") == "center", "center anchor_to missing: %s" % path


def main():
    source = PY_PATH.read_text(encoding="utf-8")
    server_source = SERVER_PATH.read_text(encoding="utf-8")
    compile(source, str(PY_PATH), "exec")
    compile(server_source, str(SERVER_PATH), "exec")
    assert "CenteredButtonAnimator" in source
    assert "CenteredButtonAnimator(self.uiName, 0.97, 1.018, CenterAnchored=True)" in source
    assert "self._PlayOpenAnimation()" in source
    assert "self._Schedule(0.38, self._EnableInteractions)" in source
    assert "self._PlayCloseAnimation()" in source
    assert "self._Schedule(0.23, self._FinishClose)" in source
    assert "if self.InteractionsEnabled and not self.Closing" in source
    assert "def _ForgetButtonBindingsUnder(self, RootPath):" in source
    assert "return UIMod.GetCompData(self.uiName, Path)" in source
    assert "UIMod.GetCompMustPosition(self.uiName, self.cfg.MainScreen)" in source
    assert "return GetCompData(self.uiName, Path)" not in source
    assert "= GetCompMustPosition(self.uiName, self.cfg.MainScreen)" not in source
    assert 'CallServer("RequestTeamManagementSnapshot"' in source
    assert 'self.ShowPage("team" if self.IsAdmin else "share", False)' in source
    assert 'READ_ONLY_PAGES = ("team", "quick", "rule")' in source
    assert "self.cfg.ReadOnlyShieldTouch" in source
    assert "AdminOnly=True" in source

    snapshot_body = method_body(
        server_source,
        "RequestTeamManagementSnapshot",
        "_PurgeExpiredConfigShares",
    )
    assert "self._RequireAdmin()" not in snapshot_body
    assert 'Snapshot["is_admin"] = self.IsAdmin(Caller)' in snapshot_body
    assert 'Snapshot.pop("operation_log", None)' in snapshot_body
    for name, next_name in [
        ("CreateTeam", "DeleteTeam"),
        ("DeleteTeam", "ToggleTeamMember"),
        ("ToggleTeamMember", "_BuildQuickGroups"),
        ("PreviewQuickAssign", "QuickAssignTeams"),
        ("QuickAssignTeams", "UndoQuickAssign"),
        ("UndoQuickAssign", "SetTeamRule"),
        ("SetTeamRule", "ReportLocalStiffState"),
    ]:
        assert "self._RequireAdmin()" in method_body(server_source, name, next_name)

    open_body = method_body(source, "Open", "Destroy")
    assert open_body.index("self._UpdateScreen()") < open_body.index("self._CaptureLayoutPositions()")
    assert open_body.index("self._CaptureLayoutPositions()") < open_body.index("self._PlayOpenAnimation()")

    list_body = method_body(source, "_PlayListEntryAnimation", "RenderTeams")
    assert "_AnimateAlpha" in list_body
    assert "_AnimateMove" not in list_body

    for name, next_name in [
        ("RenderTeams", "_RenderTeamAvatars"),
        ("RenderPlayers", "_MakeTogglePlayerCallback"),
        ("RenderRules", "_UpdateRuleToggleStates"),
    ]:
        body = method_body(source, name, next_name)
        assert "_AnimateListEntries" in body
        assert "_AnimateMove" not in body
        assert body.index("self._UpdateScreen()") < body.index("self._BindAnimatedButton(")

    data = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    animation_source = ANIMATION_PATH.read_text(encoding="utf-8")
    assert "TargetPos = BasePos if self.CenterAnchored" in animation_source
    control = data["main"]["controls"][0]["Control"]
    assert_alpha_chain(control, "/Control")
    main_screen = control_children(control)["MainScreen"]
    content = control_children(main_screen)["Content"]
    read_only_shield = control_children(content)["ReadOnlyShield"]
    assert read_only_shield.get("visible") is False
    assert read_only_shield.get("size") == ["100%", "100%"]
    assert {"Touch@TeamSystem.touch_blocker", "PermissionLabel"}.issubset(
        set(control_children(read_only_shield))
    )
    for template in [
        "text_button@common.button",
        "close_button@common.button",
        "touch_blocker@common.button",
        "member_avatar",
        "team_row",
        "player_row",
        "rule_row",
    ]:
        assert_alpha_chain(data[template], "/" + template)

    for template_name in ["text_button@common.button", "close_button@common.button"]:
        children = control_children(data[template_name])
        for prefix in ["default@", "hover@", "pressed@", "button_label@"]:
            name = [key for key in children if key.startswith(prefix)][0]
            assert_center_anchor(children[name], "/%s/%s" % (template_name, name))
    close_children = control_children(data["close_button@common.button"])
    assert_center_anchor(close_children["image"], "/close_button@common.button/image")
    for name in ["Off", "On"]:
        controls = find_named_controls(data, name)
        assert len(controls) >= 2
        for index, node in enumerate(controls):
            assert_center_anchor(node, "/%s[%s]" % (name, index))

    print("team system animation checks: pass")


if __name__ == "__main__":
    main()
