# coding=utf-8
"""Static and pure-data regressions for the global player config-share flow."""
from __future__ import print_function

import importlib.util
import copy
import json
import sys
import types
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
SERVER_PATH = ROOT / "src/SwordSoul_NewERA_B/SwordSoulFightScripts/TeamSystem/Server.py"
PROTOCOL_PATH = ROOT / "src/SwordSoul_NewERA_B/SwordSoulFightScripts/TeamSystem/ConfigShareProtocol.py"
CLIENT_PATH = ROOT / "src/SwordSoul_NewERA_B/SwordSoulFightScripts/UISystem/ConfigShare.py"
TEAM_PATH = ROOT / "src/SwordSoul_NewERA_B/SwordSoulFightScripts/UISystem/TeamSystem.py"
CONFIG_PATH = ROOT / "src/SwordSoul_NewERA_B/SwordSoulFightScripts/UISystem/UIConfig.py"
MOD_MAIN_PATH = ROOT / "src/SwordSoul_NewERA_B/SwordSoulFightScripts/modMain.py"
TEAM_JSON_PATH = ROOT / "src/SwordSoul_NewERA_R/ui/TeamSystem.json"
PROMPT_JSON_PATH = ROOT / "src/SwordSoul_NewERA_R/ui/ConfigShare.json"
UI_DEFS_PATH = ROOT / "src/SwordSoul_NewERA_R/ui/_ui_defs.json"


def load_protocol():
    spec = importlib.util.spec_from_file_location("config_share_protocol", str(PROTOCOL_PATH))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_client_module(protocol, components):
    """Load ConfigShare.py with tiny engine stubs so export/apply can be exercised off-game."""
    package_names = [
        "SwordSoulFightScripts",
        "SwordSoulFightScripts.UISystem",
        "SwordSoulFightScripts.QingYunModLibs",
        "SwordSoulFightScripts.QingYunModLibs.Plugins",
        "SwordSoulFightScripts.TeamSystem",
    ]
    for name in package_names:
        module = types.ModuleType(name)
        module.__path__ = []
        sys.modules[name] = module

    class FakeClientApi(object):
        @staticmethod
        def GetLocalPlayerId():
            return "local_player"

        @staticmethod
        def GetMinecraftEnum():
            return types.SimpleNamespace(KeyBoardType=types.SimpleNamespace(KEY_ESCAPE=1))

    client_mod = types.ModuleType("SwordSoulFightScripts.QingYunModLibs.ClientMod")
    client_mod.clientApi = FakeClientApi
    client_mod.ClientApi = types.SimpleNamespace(
        World=types.SimpleNamespace(Message=types.SimpleNamespace(SetTipMessage=lambda message: None))
    )
    client_mod.GetComponent = lambda name: components.get(name)
    client_mod.Call = lambda target: (lambda function: function)
    client_mod.CallServer = lambda *args, **kwargs: None
    client_mod.CreateTimer = lambda *args, **kwargs: None
    client_mod.DestroyTimer = lambda *args, **kwargs: None
    sys.modules[client_mod.__name__] = client_mod

    ui_mod = types.ModuleType("SwordSoulFightScripts.QingYunModLibs.UIScreen")
    ui_mod.UIScreen = type("UIScreen", (object,), {})
    sys.modules[ui_mod.__name__] = ui_mod
    sys.modules["SwordSoulFightScripts.QingYunModLibs"].UIScreen = ui_mod

    animation_mod = types.ModuleType("SwordSoulFightScripts.QingYunModLibs.UIAnimation")
    animation_mod.CenteredButtonAnimator = type("CenteredButtonAnimator", (object,), {})
    sys.modules[animation_mod.__name__] = animation_mod
    keyboard_mod = types.ModuleType("SwordSoulFightScripts.QingYunModLibs.Plugins.KeyBoardPlugins")
    keyboard_mod.KeyBoardClient = types.SimpleNamespace(AddKeyFuncBind=lambda *args: None)
    sys.modules[keyboard_mod.__name__] = keyboard_mod

    sys.modules["SwordSoulFightScripts.TeamSystem.ConfigShareProtocol"] = protocol
    config_mod = types.ModuleType("SwordSoulFightScripts.Config")
    config_mod.DefaultAnimateDict = {}
    config_mod.DefaultAnimateOrderDict = {}
    config_mod.DefaultTrailDict = {}
    config_mod.DefaultTrailOrderDict = {}
    sys.modules[config_mod.__name__] = config_mod
    ui_config_mod = types.ModuleType("UIConfig")
    ui_config_mod.ConfigShareConfig = type("ConfigShareConfig", (object,), {"uiName": "ConfigShare", "uiDef": "ConfigShare.main"})
    sys.modules[ui_config_mod.__name__] = ui_config_mod

    spec = importlib.util.spec_from_file_location(
        "SwordSoulFightScripts.UISystem.ConfigShareUnderTest", str(CLIENT_PATH)
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class RuntimeConfigMap(dict):
    """模拟网易运行时可读取、可遍历，但不保证支持 copy.deepcopy 的配置代理。"""

    def __deepcopy__(self, memo):
        raise TypeError("runtime config proxy cannot be deep-copied")


class FakeWeaponData(object):
    def __init__(self):
        self.WeaponUseFightDict = {"old:item": False}
        self.WeaponAttackSortDict = RuntimeConfigMap({"knife": {"旧动作": [1, 2, 3, 4, 5]}})
        self.WeaponAttackSortOrderDict = {"knife": ["旧动作"]}
        self.WeaponUsingAttackSortDict = {"old:item": [1, 2, 3, 4, 5]}
        self.WeaponSkillDict = {"old:item": "old_skill"}
        self.WeaponSuperSkillDict = {"old:item": "old_super"}
        self.saved = []

    def _saveConfig(self, name):
        self.saved.append(name)

    def _getConfigOrder(self, config_map, order):
        return [name for name in order if name in config_map] + [name for name in config_map if name not in order]


class FakeTrailData(object):
    def __init__(self):
        self.TrailConfig = RuntimeConfigMap({"knife": {
            "旧刀光": [{"width": 1.0}],
            "损坏结构": {"width": 2.0},
            "损坏数据": [{"bad": object()}],
        }})
        self.TrailConfigOrder = {"knife": ["损坏结构", "旧刀光", "损坏数据"]}
        self.ItemTrailConfigId = {
            "old:item": "旧刀光",
            "broken:item": "损坏结构",
        }
        self.fail_refresh = False
        self.refresh_count = 0

    def _getConfigOrder(self, config_map, order):
        return [name for name in order if name in config_map] + [name for name in config_map if name not in order]

    def UpdateWeaponTrailSuper(self):
        self.refresh_count += 1
        if self.fail_refresh:
            raise RuntimeError("trail refresh failed")


class FakeChooseSettings(object):
    def __init__(self):
        self.values = {
            "TalentPhysical": [0, 0, 0],
            "TalentDefense": [0, 0, 0],
            "TalentAttack": [0, 0, 0],
        }
        self.events = []

    def getChoose(self, key, default=None):
        return self.values.get(key, default)

    def updateChoose(self, key, value):
        self.values[key] = list(value)

    def _onTalentChanged(self, key, value, reason):
        self.events.append((key, list(value), reason))


class FakePlayerRoot(object):
    def __init__(self):
        self.refresh_count = 0

    def ChangeItem(self):
        self.refresh_count += 1


def method_body(source, name, next_name):
    start = source.index("    def %s(" % name)
    end = source.index("    def %s(" % next_name, start)
    return source[start:end]


def child_map(node):
    result = {}
    for item in node.get("controls", []):
        for raw_name, child in item.items():
            result[raw_name.split("@", 1)[0]] = child
    return result


def resolve(root, path):
    node = root
    for name in [part for part in path.split("/") if part]:
        node = child_map(node)[name]
    return node


def assert_alpha_chain(node, path):
    controls = node.get("controls") if isinstance(node, dict) else None
    if controls is None:
        return
    assert node.get("propagate_alpha") is True, "alpha propagation break: %s" % path
    for item in controls:
        for name, child in item.items():
            assert_alpha_chain(child, path + "/" + name)


def sample_payload():
    return {
        "schema_version": 1,
        "categories": {
            "combat": {
                "WeaponUseFightDict": {"minecraft:iron_sword": True},
                "WeaponAttackSortDict": {"knife": {"自定义": (1, 3, 2, 4, 5)}},
                "WeaponAttackSortOrderDict": {"knife": ["自定义"]},
                "WeaponUsingAttackSortDict": {"minecraft:iron_sword": [1, 3, 2, 4, 5]},
                "TrailConfig": {"knife": {"蓝色": [{"width": 1.0, "offset": (0, 0, 0)}]}},
                "TrailConfigOrder": {"knife": ["蓝色"]},
                "ItemTrailConfigId": {"minecraft:iron_sword": "蓝色"},
            },
            "talent": {
                "TalentPhysical": [5, 2, 0],
                "TalentDefense": [3, 1, 0],
                "TalentAttack": [4, 3, 2],
            },
            "skills": {
                "WeaponSkillDict": {"minecraft:iron_sword": "knife_skill"},
                "WeaponSuperSkillDict": {"minecraft:iron_sword": "knife_super"},
            },
        },
    }


def main():
    protocol = load_protocol()
    payload, error = protocol.ValidateSharePayload(sample_payload())
    assert error is None
    assert isinstance(payload["categories"]["combat"]["WeaponAttackSortDict"]["knife"]["自定义"], list)
    assert protocol.GetSelectedCategories(payload) == ["combat", "talent", "skills"]

    invalid = sample_payload()
    invalid["categories"]["talent"]["TalentAttack"] = [5, 5, 5]
    assert protocol.ValidateSharePayload(invalid)[1] == "天赋点数超过20点上限"
    invalid = sample_payload()
    invalid["categories"]["unknown"] = {}
    assert protocol.ValidateSharePayload(invalid)[1] == "分享数据包含未知配置类别"
    invalid = sample_payload()
    invalid["categories"]["combat"]["TrailConfig"]["knife"]["蓝色"][0]["bad"] = object()
    assert protocol.ValidateSharePayload(invalid)[1] == "配置包含不支持的数据类型"

    weapon = FakeWeaponData()
    trail = FakeTrailData()
    choose = FakeChooseSettings()
    player_root = FakePlayerRoot()
    components = {
        "WeaponDataSystem": weapon,
        "TrailDataSystem": trail,
        "ChooseSettingSystem": choose,
        "PlayerRootController": player_root,
    }
    client_module = load_client_module(protocol, components)
    exported = client_module.BuildPlayerConfigSharePayload(["combat", "talent", "skills"])
    assert protocol.GetSelectedCategories(exported) == ["combat", "talent", "skills"]
    exported_combat = exported["categories"]["combat"]
    assert exported_combat["TrailConfig"] == {"knife": {"旧刀光": [{"width": 1.0}]}}
    assert exported_combat["TrailConfigOrder"] == {"knife": ["旧刀光"]}
    assert exported_combat["ItemTrailConfigId"] == {"old:item": "旧刀光"}

    # 接收者自己含坏刀光时仍可创建回滚快照；应用失败必须原样恢复旧对象。
    invalid_trail_reference = trail.TrailConfig
    trail.fail_refresh = True
    try:
        client_module.ApplyPlayerConfigSharePayload(sample_payload())
        raise AssertionError("expected refresh failure with invalid local trail")
    except RuntimeError:
        pass
    assert trail.TrailConfig is invalid_trail_reference
    trail.fail_refresh = False

    applied = client_module.ApplyPlayerConfigSharePayload(sample_payload())
    assert applied == ["combat", "talent", "skills"]
    assert weapon.WeaponSkillDict == {"minecraft:iron_sword": "knife_skill"}
    assert trail.ItemTrailConfigId == {"minecraft:iron_sword": "蓝色"}
    assert choose.values["TalentPhysical"] == [5, 2, 0]
    assert player_root.refresh_count == 1

    before_weapon = copy.deepcopy(weapon.WeaponAttackSortDict)
    before_trail = copy.deepcopy(trail.TrailConfig)
    before_talent = copy.deepcopy(choose.values)
    trail.fail_refresh = True
    rollback_payload = sample_payload()
    rollback_payload["categories"]["combat"]["WeaponAttackSortDict"] = {"knife": {"不应保留": [5, 4, 3, 2, 1]}}
    try:
        client_module.ApplyPlayerConfigSharePayload(rollback_payload)
        raise AssertionError("expected refresh failure")
    except RuntimeError:
        pass
    assert weapon.WeaponAttackSortDict == before_weapon
    assert trail.TrailConfig == before_trail
    assert choose.values == before_talent

    server_source = SERVER_PATH.read_text(encoding="utf-8")
    client_source = CLIENT_PATH.read_text(encoding="utf-8")
    team_source = TEAM_PATH.read_text(encoding="utf-8")
    config_source = CONFIG_PATH.read_text(encoding="utf-8")
    for source, path in [
        (server_source, SERVER_PATH),
        (client_source, CLIENT_PATH),
        (team_source, TEAM_PATH),
        (config_source, CONFIG_PATH),
    ]:
        compile(source, str(path), "exec")

    share_server = method_body(server_source, "SharePlayerConfigs", "RespondConfigShare")
    assert "self._RequireAdmin()" not in share_server
    assert "Caller not in OnlineSet" in share_server
    assert "MAX_SHARE_TARGETS" in share_server
    assert 'CallClient("ReceiveConfigShareProposal"' in share_server
    respond_server = method_body(server_source, "RespondConfigShare", "CreateTeam")
    assert 'get("check_only", False)' in respond_server
    assert 'CallClient("ConfigShareResponse"' in respond_server

    accept_body = method_body(client_source, "Accept", "_OnAcceptAuthorized")
    authorized_body = method_body(client_source, "_OnAcceptAuthorized", "Reject")
    assert '"check_only": True' in accept_body
    assert authorized_body.index("ApplyPlayerConfigSharePayload") < authorized_body.index('"accepted": True')
    assert "config_share_rollback" in client_source
    assert "ReceiveConfigShareProposal" in client_source
    assert "_PENDING_PROPOSALS" in client_source

    assert 'self.ShowPage("share")' in team_source
    assert "ShareSelectedPlayers" in team_source
    assert "SHARE_MAX_TARGETS" in team_source
    assert 'PlayerData.get("player_id") == playerId' in team_source
    assert 'CallServer("SharePlayerConfigs"' in team_source
    assert "BuildPlayerConfigSharePayload" in team_source

    team_json = json.loads(TEAM_JSON_PATH.read_text(encoding="utf-8"))
    main_screen = resolve(team_json["main"], "/Control/MainScreen")
    header_names = set(child_map(child_map(main_screen)["Header"]).keys())
    content_names = set(child_map(child_map(main_screen)["Content"]).keys())
    assert "ShareScreen" not in header_names
    assert content_names == {"TeamScreen", "QuickScreen", "RuleScreen", "ShareScreen", "ReadOnlyShield"}
    tabs = child_map(main_screen)["Tabs"]
    assert {"TeamMenu", "QuickMenu", "RuleMenu", "ShareMenu"}.issubset(set(child_map(tabs)))
    share_screen = child_map(child_map(main_screen)["Content"])["ShareScreen"]
    share_columns = child_map(share_screen)
    assert share_columns["Categories"].get("size") == ["44%", "100%-30px"]
    assert share_columns["Players"].get("size") == ["54%", "100%-30px"]
    assert share_columns["Players"].get("anchor_from") == "top_right"
    assert_alpha_chain(team_json["main"]["controls"][0]["Control"], "/Control")
    for template_name in ("share_option_row", "share_player_row@TeamSystem.share_option_row"):
        assert_alpha_chain(team_json[template_name], "/" + template_name)

    prompt_json = json.loads(PROMPT_JSON_PATH.read_text(encoding="utf-8"))
    prompt_control = prompt_json["main"]["controls"][0]["Control"]
    assert_alpha_chain(prompt_control, "/Control")
    prompt_children = child_map(prompt_control)
    assert "MainPanel" in prompt_children
    assert prompt_children["Shield"].get("layer") < prompt_children["MainPanel"].get("layer")
    assert not any(name.lower().startswith("dim") for name in prompt_children)
    panel_children = child_map(prompt_children["MainPanel"])
    assert {"Close", "Accept", "Reject", "CategoryText"}.issubset(set(panel_children))

    assert 'Mod.ClientInit("UISystem.ConfigShare")' in MOD_MAIN_PATH.read_text(encoding="utf-8")
    assert "ui/ConfigShare.json" in json.loads(UI_DEFS_PATH.read_text(encoding="utf-8"))["ui_defs"]
    print("config share checks: pass")


if __name__ == "__main__":
    main()
