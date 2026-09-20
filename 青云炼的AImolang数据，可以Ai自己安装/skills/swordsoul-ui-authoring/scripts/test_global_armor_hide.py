# coding=utf-8
"""Focused regression checks for global player armor visibility synchronization."""
from __future__ import print_function

from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
SCRIPT_ROOT = ROOT / "src/SwordSoul_NewERA_B/SwordSoulFightScripts"
GENERAL_PATH = SCRIPT_ROOT / "UISystem/GeneralScreen.py"
SETTING_PATH = SCRIPT_ROOT / "UISystem/SettingData.py"
SERVER_PATH = SCRIPT_ROOT / "FightSystem/FightServer.py"
CLIENT_ROOT_PATH = SCRIPT_ROOT / "SwordSoulClient.py"
RENDER_PATH = SCRIPT_ROOT / "QingYunModLibs/RenderSystem/BaseApi.py"


def method_source(source, name):
    start = source.index("    def %s(" % name)
    tail = source[start:].splitlines()
    lines = []
    for index, line in enumerate(tail):
        if index and (line.startswith("    def ") or line.startswith("    @")):
            break
        lines.append(line)
    return "\n".join(lines) + "\n"


def build_client_harness(setting_source):
    names = (
        "_NormalizeArmorVisibility",
        "ReapplyArmorVisibility",
        "SyncGlobalArmorVisibilityClient",
        "OnPlayerRenderResourcesReloaded",
    )
    namespace = {"playerId": "local"}
    exec("class Harness(object):\n" + "".join(method_source(setting_source, name) for name in names), namespace)
    return namespace["Harness"]


def build_server_harness(server_source):
    calls = []

    def call_all(name, data):
        calls.append(("all", name, data))

    def call_client(name, target, data):
        calls.append(("one", name, target, data))

    names = (
        "_NormalizeArmorVisibility",
        "GetGlobalArmorVisibilityData",
        "BroadcastGlobalArmorVisibility",
        "UpdatePlayerArmorVisibility",
        "SyncGlobalArmorVisibility",
    )
    namespace = {"CallAllClient": call_all, "CallClient": call_client}
    exec("class Harness(object):\n" + "".join(method_source(server_source, name) for name in names), namespace)
    return namespace["Harness"], calls


def main():
    general_source = GENERAL_PATH.read_text(encoding="utf-8")
    setting_source = SETTING_PATH.read_text(encoding="utf-8")
    server_source = SERVER_PATH.read_text(encoding="utf-8")
    client_root_source = CLIENT_ROOT_PATH.read_text(encoding="utf-8")
    render_source = RENDER_PATH.read_text(encoding="utf-8")

    # The rule is visible, persisted through the existing rule-setting path, and defaults on at every layer.
    assert '"id": "AllowGlobalArmorHide"' in general_source
    assert '"label": "允许全局盔甲隐藏"' in general_source
    assert '"default_value": True' in general_source[general_source.index('"id": "AllowGlobalArmorHide"'):]
    assert 'self.AllowGlobalArmorHide = True' in setting_source
    assert 'self.SetLocalConfig("AllowGlobalArmorHide", True, False)' in setting_source
    assert 'self.RuleSettingMap = {"AllowGlobalArmorHide": True}' in server_source

    ClientHarness = build_client_harness(setting_source)
    client = ClientHarness()
    client._ArmorSlotSettings = (
        (0, "ShowHelmet"),
        (1, "ShowBreastplate"),
        (2, "ShowLegs"),
        (3, "ShowBoots"),
    )
    own = {
        "ShowHelmet": False,
        "ShowBreastplate": True,
        "ShowLegs": False,
        "ShowBoots": True,
    }
    client.GetOwnArmorVisibility = lambda: dict(own)
    applied = []
    client._ApplyArmorSlotVisibility = lambda entity, slot, show: applied.append((entity, slot, show))
    client.GlobalArmorHideEnabled = True
    client.GlobalArmorVisibilityMap = {}

    # A full snapshot applies remote preferences but never overwrites the local player's own selection.
    client.SyncGlobalArmorVisibilityClient({
        "enabled": True,
        "players": {
            "local": dict((key, True) for key in own),
            "remote": {
                "ShowHelmet": False,
                "ShowBreastplate": False,
                "ShowLegs": True,
                "ShowBoots": True,
            },
        },
    })
    local_values = [show for entity, slot, show in applied if entity == "local"]
    remote_values = [show for entity, slot, show in applied if entity == "remote"]
    assert local_values == [False, True, False, True]
    assert remote_values == [False, False, True, True]

    # Turning the rule off restores all previously known remote slots while preserving the local choice.
    applied[:] = []
    client.SyncGlobalArmorVisibilityClient({"enabled": False, "players": {}})
    assert [show for entity, slot, show in applied if entity == "remote"] == [True, True, True, True]
    assert [show for entity, slot, show in applied if entity == "local"] == [False, True, False, True]

    # A render snapshot rebuild replays the cached desired state for that exact player.
    applied[:] = []
    client.OnPlayerRenderResourcesReloaded("remote")
    assert [show for entity, slot, show in applied] == [True, True, True, True]

    ServerHarness, calls = build_server_harness(server_source)
    server = ServerHarness()
    server.RuleSettingMap = {"AllowGlobalArmorHide": False}
    server.PlayerArmorVisibilityMap = {}
    server.UpdatePlayerArmorVisibility({"playerId": "remote", "visibility": {"ShowHelmet": False}})
    assert server.PlayerArmorVisibilityMap["remote"]["ShowHelmet"] is False
    assert calls == [], "disabled rule must cache preferences without changing observers"

    server.RuleSettingMap["AllowGlobalArmorHide"] = True
    server.BroadcastGlobalArmorVisibility()
    assert calls[-1][0:2] == ("all", "SyncGlobalArmorVisibilityClient")
    assert calls[-1][2]["players"]["remote"]["ShowHelmet"] is False
    server.SyncGlobalArmorVisibility("late_joiner")
    assert calls[-1][0:3] == ("one", "SyncGlobalArmorVisibilityClient", "late_joiner")

    # Resource and AOI repair hooks must run after rebuild and request a fresh snapshot on player creation.
    rebuild_index = render_source.index("RenderComp.RebuildPlayerRender()")
    replay_index = render_source.index("_NotifyPlayerRenderResourcesReloaded(PlayerId)", rebuild_index)
    assert rebuild_index < replay_index
    created_body = method_source(setting_source, "OnGlobalArmorPlayerCreated")
    assert 'CallServer("SyncGlobalArmorVisibility", playerId)' in created_body
    assert "CreateTimer(0.25" in created_body and "CreateTimer(1.0" in created_body
    assert client_root_source.index("PR.RebuildPlayerRenderController(True)") < client_root_source.index(
        "ChooseSettingSystem.ReapplyArmorVisibility(playerId)"
    )

    print("global armor hide checks: pass")


if __name__ == "__main__":
    main()
