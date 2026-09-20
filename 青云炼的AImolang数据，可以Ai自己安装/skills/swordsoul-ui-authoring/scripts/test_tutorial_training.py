#!/usr/bin/env python3
"""临时训练场、青云木偶、阶段提示与资源联动回归。"""

from __future__ import print_function

import ast
import copy
import json
import math
import re
import runpy
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
BEHAVIOR = ROOT / "src/SwordSoul_NewERA_B"
RESOURCE = ROOT / "src/SwordSoul_NewERA_R"
FIGHT = BEHAVIOR / "SwordSoulFightScripts"
MOB = BEHAVIOR / "SwordSoulMobFightScripts"


def source(path):
    return path.read_text(encoding="utf-8-sig")


def require(text, snippet):
    assert snippet in text, "missing training contract: %s" % snippet


def load_catalog():
    path = FIGHT / "UISystem/TutorialCatalog.py"
    return runpy.run_path(str(path))["TUTORIAL_CATALOG"]


def load_runtime_method(path, class_name, method_name):
    tree = ast.parse(source(path))
    class_node = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == class_name)
    method_node = next(node for node in class_node.body if isinstance(node, ast.FunctionDef) and node.name == method_name)
    method_node.decorator_list = []
    runtime_class = ast.ClassDef(
        name="RuntimeProbe",
        bases=[],
        keywords=[],
        body=[method_node],
        decorator_list=[],
    )
    namespace = {}
    module = ast.Module(body=[runtime_class], type_ignores=[])
    exec(compile(ast.fix_missing_locations(module), str(path), "exec"), namespace)
    return getattr(namespace["RuntimeProbe"], method_name)


def visible_strings(value):
    visible_keys = {
        "title", "summary", "caption", "details", "input_hint", "instruction",
        "hint", "success", "retry", "label", "watch", "prompt",
    }
    if isinstance(value, dict):
        for key, child in value.items():
            if key in visible_keys and isinstance(child, str):
                yield child
            for text in visible_strings(child):
                yield text
    elif isinstance(value, list):
        for child in value:
            for text in visible_strings(child):
                yield text


def assert_alpha_chain(control, path):
    if not isinstance(control, dict):
        return
    children = control.get("controls", [])
    if children:
        assert control.get("propagate_alpha") is True, "broken alpha chain: %s" % path
    for child_entry in children:
        for name, child in child_entry.items():
            assert_alpha_chain(child, path + "/" + name.split("@", 1)[0])


def main():
    behavior_entity = json.loads(source(BEHAVIOR / "entities/arris_training_dummy.json"))
    client_entity = json.loads(source(RESOURCE / "entity/arris_training_dummy.json"))
    description = behavior_entity["minecraft:entity"]["description"]
    components = behavior_entity["minecraft:entity"]["components"]
    assert description["identifier"] == "arris:training_dummy"
    assert description["is_spawnable"] is True
    assert description["is_summonable"] is True
    assert components["minecraft:health"]["max"] >= 1000000
    assert components["minecraft:attack"]["damage"] == 1
    assert components["minecraft:knockback_resistance"]["value"] == 1.0
    assert not any(name.startswith("minecraft:behavior.") for name in components)
    assert client_entity["minecraft:client_entity"]["description"]["identifier"] == "arris:training_dummy"
    assert client_entity["minecraft:client_entity"]["description"].get("spawn_egg")

    mob_entity_source = source(MOB / "Entities/QingYunMob.py")
    mob_server_source = source(MOB / "SwordSoulMobServer.py")
    for snippet in (
        '@MobEntityRegistry.Entity(TRAINING_DUMMY_ENTITY_TYPE, "training_dummy")',
        "class TrainingDummyMob(QingYunMob):",
        "self.sense = None",
        "self.ai_core = None",
        "return QINGYUN_ENTITY_TYPE",
    ):
        require(mob_entity_source, snippet)
    require(mob_server_source, "def OnTrainingDummyHealthChange(self, args):")
    require(mob_server_source, "if toHealth <= 0:")
    require(mob_server_source, 'args["cancel"] = True')
    require(mob_server_source, 'args["knock"] = False')
    assert mob_server_source.index("if toHealth <= 0:") < mob_server_source.index('args["cancel"] = True')

    arena_source = source(FIGHT / "TutorialTrainingServer.py")
    for snippet in (
        "ARENA_SIZE = 32",
        "ARENA_WALL_HEIGHT = 12",
        "ARENA_ENTRY_TELEPORT_DELAY = 0.5",
        "FloorY = int(Highest) + 20",
        "FloorY + ARENA_WALL_HEIGHT + 1",
        "range(1, ARENA_WALL_HEIGHT + 1)",
        "Snapshot = self._snapshotBlocks",
        "Built, Written = self._writeArena",
        "def _restoreBlocks(self, Session):",
        "def _retryBlockRestore(self, PlayerId):",
        "def _getSafeReturnPos(self, Session):",
        'TUTORIAL_TRAINING_ITEM = "minecraft:diamond_sword"',
        '"reaction": {"item": TUTORIAL_TRAINING_ITEM',
        '"state": "fight_attack_fourteenth", "impact_at": 0.54',
        "def _snapshotPlayerInventory(self, PlayerId):",
        "def _equipPlayerTrainingWeapon(self, PlayerId, Session):",
        "def _restorePlayerInventory(self, PlayerId, Session):",
        "def _retryPendingPlayerReturn(self, PlayerId):",
        "def _enterArena(self, PlayerId):",
        "if PlayerId in self.PendingReturns:",
        '"return_inventory": ReturnInventory',
        '"return_selected_slot": ReturnSelectedSlot',
        'GetVaryingClient("_CallerPlayerId_Listen"',
        "def EndTutorialTraining(self, Args):",
        'ComponentListenEvent("PlayerIntendLeaveServerEvent")',
        'ComponentListenEvent("DelServerPlayerEvent")',
        "def _cleanupLeavingPlayer(self, PlayerId):",
        '"return_game_type": ReturnGameType',
        "def DestroyComponent(self):",
        'Mob.execute_fight_state(Move["state"]',
        '"ignore_skill_cd": True',
        '"player_combo"',
        "Mob.command_translator.StiffStack = 0.0",
        "Mob.command_translator.StiffProtectState = False",
        'return self._runDummyMove(PlayerId, StepToken, "reaction")',
        '"reaction" if CueType == "attack" else "clash_low"',
        'WindowDuration = max(WindowDuration, float(TUTORIAL_REAL_MOVES["reaction"].get("impact_at", 0.54)))',
        '"entry_ready": False',
        '"ready_delay": ARENA_ENTRY_TELEPORT_DELAY + 0.1',
    ):
        require(arena_source, snippet)
    assert arena_source.index("Snapshot = self._snapshotBlocks") < arena_source.index("Built, Written = self._writeArena")
    cleanup_source = arena_source[
        arena_source.index("def _cleanupSession(self, PlayerId, RestorePlayer=True):"):
        arena_source.index("def BeginTutorialTraining(self, Args):")
    ]
    assert cleanup_source.index("ServerObj.DestroyEntity(DummyId)") < cleanup_source.index("self._restoreBlocks(Session)")

    system_source = source(FIGHT / "QingYunModLibs/SystemApi.py")
    require(system_source, 'ListenServerEvents("DelServerPlayerEvent", DestroyAllServerEvents)')
    assert 'ListenServerEvents("PlayerIntendLeaveServerEvent", DestroyAllServerEvents)' not in system_source

    training_path = FIGHT / "TutorialTrainingServer.py"
    begin_source = arena_source[
        arena_source.index("def BeginTutorialTraining(self, Args):"):
        arena_source.index("def _faceEntities(self, Session, PlayerId):")
    ]
    assert begin_source.index("if PlayerId in self.Sessions:") < begin_source.index("self._cleanupSession(PlayerId, True)")
    assert begin_source.index("if PlayerId in self.PendingReturns:") < begin_source.index("ReturnPos = ServerApi.Entity.Attribute.GetFootPos(PlayerId)")
    assert begin_source.index("Built, Written = self._writeArena") < begin_source.index("ARENA_ENTRY_TELEPORT_DELAY,")
    assert 'SetFootPos(PlayerId, Session["player_pos"])' not in begin_source
    assert "ServerEvents.EntityEvents.ActuallyHurtServerEvent" in arena_source
    assert "ServerEvents.EntityEvents.HealthChangeBeforeServerEvent" not in arena_source
    assert "ServerEvents.EntityEvents.DamageEvent" not in arena_source
    assert 'args["cancel"]' not in arena_source.lower()

    health_handler = load_runtime_method(training_path, "TutorialTrainingServerSystem", "OnTrainingPlayerActuallyHurt")
    health_probe = type("HealthProbe", (), {})()
    health_probe.Sessions = {"player": {}}
    attr_probe = type("AttrProbe", (), {"GetAttrValue": lambda self, attr_type: self.health})()
    attr_probe.health = 20.0
    server_comp_probe = type("ServerCompProbe", (), {"CreateAttr": staticmethod(lambda player_id: attr_probe)})
    enum_probe = type("EnumProbe", (), {"AttrType": type("AttrTypeProbe", (), {"HEALTH": "health"})})
    server_api_probe = type("ServerApiProbe", (), {"GetMinecraftEnum": staticmethod(lambda: enum_probe)})
    health_handler.__globals__["ServerComp"] = server_comp_probe
    health_handler.__globals__["serverApi"] = server_api_probe
    normal_damage = {"entityId": "player", "damage": 2, "damage_f": 2.0}
    health_handler(health_probe, normal_damage)
    assert normal_damage == {"entityId": "player", "damage": 2, "damage_f": 2.0}
    attr_probe.health = 6.0
    lethal_damage = {"entityId": "player", "damage": 8, "damage_f": 8.0}
    health_handler(health_probe, lethal_damage)
    assert lethal_damage["damage"] == 5.0
    assert lethal_damage["damage_f"] == 5.0
    assert "cancel" not in lethal_damage

    begin_handler = load_runtime_method(training_path, "TutorialTrainingServerSystem", "BeginTutorialTraining")
    begin_probe = type("BeginProbe", (), {})()
    begin_probe.Sessions = {"player": {"page_id": "armor_training"}}
    begin_probe._getCallerPlayer = lambda args: "player"
    alive_probe = type("AliveProbe", (), {"IsEntityAlive": staticmethod(lambda entity_id: True)})
    world_probe = type("WorldProbe", (), {"Entity": alive_probe})
    begin_handler.__globals__["ServerApi"] = type("BeginServerApiProbe", (), {"World": world_probe})
    duplicate_result = begin_handler(begin_probe, {"playerId": "player", "page_id": "stiff_training"})
    assert duplicate_result == {"ok": False, "message": "实机教学已经开始，请先退出当前教学"}
    assert begin_probe.Sessions["player"]["page_id"] == "armor_training"

    # Codex 2026-07-24: 延迟入场只执行一次，并且必须先落位、清速度、校正朝向，最后才开放教学步骤。
    enter_handler = load_runtime_method(training_path, "TutorialTrainingServerSystem", "_enterArena")
    enter_probe = type("EnterProbe", (), {})()
    enter_probe.Sessions = {"player": {"entry_ready": False, "player_pos": (1.5, 80.01, -2.5)}}
    enter_actions = []
    enter_probe._faceEntities = lambda session, player_id: enter_actions.append(("face", player_id))
    enter_attribute = type("EnterAttributeProbe", (), {
        "SetFootPos": staticmethod(lambda player_id, pos: enter_actions.append(("position", player_id, pos)))
    })
    enter_action = type("EnterActionProbe", (), {
        "SetMotion": staticmethod(lambda player_id, motion: enter_actions.append(("motion", player_id, motion)))
    })
    enter_entity = type("EnterEntityProbe", (), {
        "IsEntityAlive": staticmethod(lambda player_id: True)
    })
    enter_handler.__globals__["ServerApi"] = type("EnterServerApiProbe", (), {
        "World": type("EnterWorldProbe", (), {"Entity": enter_entity}),
        "Entity": type("EnterEntityApiProbe", (), {"Attribute": enter_attribute, "Action": enter_action})
    })
    enter_handler(enter_probe, "player")
    assert enter_actions == [
        ("position", "player", (1.5, 80.01, -2.5)),
        ("motion", "player", (0.0, 0.0, 0.0)),
        ("face", "player"),
    ]
    assert enter_probe.Sessions["player"]["entry_ready"] is True
    enter_handler(enter_probe, "player")
    assert len(enter_actions) == 3

    # Codex 2026-07-22: 钻石剑只占用玩家原本选中槽，结束时包括空槽与选中位置一起精确还原。
    equip_inventory = load_runtime_method(training_path, "TutorialTrainingServerSystem", "_equipPlayerTrainingWeapon")
    restore_inventory = load_runtime_method(training_path, "TutorialTrainingServerSystem", "_restorePlayerInventory")
    inventory_slots = {
        (0, 0): {"newItemName": "minecraft:iron_sword", "count": 1},
        (0, 1): None,
    }
    selected_slot = [0]

    class KnapsackProbe(object):
        @staticmethod
        def SetPlayerAllItems(player_id, item_map):
            inventory_slots.update(copy.deepcopy(item_map))

        @staticmethod
        def GetPlayerItem(player_id, item_pos_type, slot, include_user_data):
            return copy.deepcopy(inventory_slots.get((item_pos_type, slot)))

        @staticmethod
        def ChangeSelectSlot(player_id, slot):
            selected_slot[0] = slot
            return True

    inventory_api = type("InventoryApiProbe", (), {
        "Player": type("InventoryPlayerProbe", (), {"Knapsack": KnapsackProbe})
    })
    inventory_session = {
        "return_inventory": [
            {"newItemName": "minecraft:iron_sword", "count": 1},
            None,
        ],
        "return_selected_slot": 0,
    }
    for handler in (equip_inventory, restore_inventory):
        handler.__globals__["ServerApi"] = inventory_api
        handler.__globals__["copy"] = copy
        handler.__globals__["TUTORIAL_TRAINING_ITEM"] = "minecraft:diamond_sword"
        handler.__globals__["TUTORIAL_TRAINING_ITEM_DATA"] = {
            "newItemName": "minecraft:diamond_sword", "itemName": "minecraft:diamond_sword", "count": 1
        }
        handler.__globals__["TUTORIAL_EMPTY_ITEM_DATA"] = {
            "newItemName": "minecraft:air", "itemName": "minecraft:air", "count": 0
        }
    assert equip_inventory(object(), "player", inventory_session) is True
    assert inventory_slots[(0, 0)]["newItemName"] == "minecraft:diamond_sword"
    inventory_slots[(0, 1)] = {"newItemName": "minecraft:dirt", "count": 64}
    selected_slot[0] = 1
    assert restore_inventory(object(), "player", inventory_session) is True
    assert inventory_slots[(0, 0)]["newItemName"] == "minecraft:iron_sword"
    assert inventory_slots[(0, 1)]["newItemName"] == "minecraft:air"
    assert selected_slot[0] == 0

    stop_moves_handler = load_runtime_method(training_path, "TutorialTrainingServerSystem", "_stopDummyPersistentMoves")
    stop_moves_probe = type("StopMovesProbe", (), {})()
    attack_timer = object()
    cancel_timer = object()
    tracked_timers = {
        "qingyun_king_deterrence_attack_timer_dummy": attack_timer,
        "qingyun_king_deterrence_cancel_timer_dummy": cancel_timer,
    }
    requested_timer_ids = []
    destroyed_timers = []
    timer_manager_probe = type("TimerManagerProbe", (), {
        "getTimer": staticmethod(lambda timer_id: requested_timer_ids.append(timer_id) or tracked_timers.get(timer_id))
    })
    stop_moves_handler.__globals__["TimerManager"] = timer_manager_probe
    stop_moves_handler.__globals__["DestroyTimer"] = lambda timer: destroyed_timers.append(timer)
    stop_moves_handler(stop_moves_probe, "dummy")
    assert requested_timer_ids == [
        "qingyun_king_deterrence_attack_timer_dummy",
        "qingyun_king_deterrence_cancel_timer_dummy",
    ]
    assert destroyed_timers == [attack_timer, cancel_timer]

    # Codex 2026-07-20: 只有教程木偶显式的强制请求能跳过生物技能CD，普通强制调用仍被拦截。
    mob_controller_path = MOB / "Combat/FightController.py"
    mob_controller_source = source(mob_controller_path)
    require(mob_controller_source, 'request.get("source") == "tutorial"')
    require(mob_controller_source, 'request.get("ignore_skill_cd", False)')
    set_state = load_runtime_method(mob_controller_path, "MobFightController", "set_state")
    state_obj = type("SkillStateObj", (), {})()
    state_wrapper = type("SkillStateWrapper", (), {"RunningStateObj": state_obj})()
    controller_probe = type("MobControllerProbe", (), {})()
    controller_probe.mob = type("MobProbe", (), {
        "entityId": "dummy",
        "HasFightState": lambda self, state_id: True,
        "get_fight_state": lambda self, state_id: state_obj,
    })()
    controller_probe.StateMap = {"fight_attack_skill": state_wrapper}
    controller_probe.StateTypeMap = {"fight_attack_skill": "skill"}
    controller_probe.NowStateId = "fight_none"
    controller_probe.is_unbreakable_execute_break_time = lambda: False
    controller_probe._can_use_skill_state = lambda state_id, running, state_type: False
    controller_probe.can_change_state = lambda state_id, force: False
    translated_requests = []
    controller_probe._translate_to_state = lambda state_id, request: translated_requests.append(
        (state_id, request)
    ) or True
    assert set_state(controller_probe, "fight_attack_skill", {"source": "other"}, True) is False
    assert set_state(controller_probe, "fight_attack_skill", {
        "source": "other", "ignore_skill_cd": True
    }, True) is False
    assert set_state(controller_probe, "fight_attack_skill", {
        "source": "tutorial", "ignore_skill_cd": True
    }, True) is True
    assert translated_requests == [("fight_attack_skill", {
        "source": "tutorial", "ignore_skill_cd": True
    })]
    assert set_state(controller_probe, "fight_attack_skill", {
        "source": "tutorial", "ignore_skill_cd": True
    }, False) is False

    player_client_source = source(FIGHT / "FightSystem/FightClient.py")
    assert "ShouldTutorialBypassSkillCooldown" not in player_client_source
    assert "self.CancelSkillCd or ShouldTutorialBypassSkillCooldown" not in player_client_source

    sequence_handler = load_runtime_method(training_path, "TutorialTrainingServerSystem", "_runDummySequenceMove")
    sequence_probe = type("SequenceProbe", (), {})()
    sequence_probe.Sessions = {"player": {"dummy_pos": (0.0, 1.0, 1.0)}}
    sequence_probe._isCurrentStep = lambda player_id, step_token: True
    sequence_calls = []
    sequence_probe._runDummyMove = lambda player_id, step_token, move_name, dummy_pos=None: sequence_calls.append(
        (player_id, step_token, move_name, dummy_pos)
    ) or True
    attribute_probe = type("AttributeProbe", (), {"GetFootPos": staticmethod(lambda entity_id: (0.0, 5.0, -2.0))})
    entity_probe = type("EntityProbe", (), {"Attribute": attribute_probe})
    sequence_handler.__globals__["ServerApi"] = type("ServerApiProbe", (), {"Entity": entity_probe})
    sequence_handler.__globals__["math"] = math
    assert sequence_handler(sequence_probe, "player", 3, "light_medium") is True
    assert sequence_calls and sequence_calls[0][:3] == ("player", 3, "light_medium")
    assert all(abs(actual - expected) < 1e-6 for actual, expected in zip(sequence_calls[0][3], (0.0, 1.0, 0.2)))

    leave_handler = load_runtime_method(training_path, "TutorialTrainingServerSystem", "_cleanupLeavingPlayer")
    leave_probe = type("LeaveProbe", (), {})()
    leave_probe.PendingReturns = {}
    cleanup_calls = []
    leave_probe._cleanupSession = lambda player_id, restore_player: cleanup_calls.append((player_id, restore_player)) or {"player": player_id}
    assert leave_handler(leave_probe, "player") is True
    assert cleanup_calls == [("player", True)]
    assert leave_probe.PendingReturns["player"]["player"] == "player"

    practice_source = source(FIGHT / "UISystem/TutorialPractice.py")
    for snippet in (
        'CallServer("BeginTutorialTraining"',
        'CallServer("PrepareTutorialTrainingStep"',
        'CallServer("EndTutorialTraining"',
        "def _renderStages(self, Surface, Step):",
        "def _showWindowCue(self, Text, Duration):",
        "def _ensureStepResources(self, Step):",
        "def _shouldSkipStep(self, Step):",
        "def _trackHitSequence(self, Step, Action, Value):",
        "self.TrainingDummyId = Result.get(\"dummy_id\")",
        "def _finishSceneReady(self, SceneToken, Result):",
        'Result.get("ready_delay", 0.0)',
        "self._restoreResources()",
        "self._returnToBook",
        "def _beginCurrentStep(self, Token, StepIndex):",
        "self.StepReady = False",
        "AdvanceDelay = float(Step.get(\"success_hold\"",
        "self._showInputPressCue(Action)",
        "self.InputCueIcon or Step.get(\"icon\"",
        'SetVisible(UiName, Config["pressed"], bool(self.InputCueIcon))',
    ):
        require(practice_source, snippet)
    require(arena_source, 'PageId.startswith("armor_")')
    require(arena_source, 'PageId.startswith("stiff_")')
    assert 'AdvanceDelay = 3.0' in practice_source
    assert 'AdvanceDelay = max(3.0, min(6.0, AdvanceDelay))' in practice_source
    complete_source = practice_source[
        practice_source.index("def _completeStep(self, Step, SuccessText=None):"):
        practice_source.index("def IsExpecting(self, Action):")
    ]
    assert complete_source.index("self.StepReady = True") < complete_source.index("CreateTimer(AdvanceDelay")
    assert complete_source.index("self._setDemoInputLocked(False)") < complete_source.index("CreateTimer(AdvanceDelay")
    assert "SetState(" not in complete_source

    ensure_resources = load_runtime_method(
        FIGHT / "UISystem/TutorialPractice.py", "TutorialPracticeSystem", "_ensureStepResources"
    )

    class FightStateMachineProbe(object):
        def __init__(self):
            self.state = "fight_attack_first"

        def getNowStateId(self):
            return self.state

        def SetState(self, state):
            self.state = state

    fight_state_machine = FightStateMachineProbe()
    fight_control_probe = type("FightControlProbe", (), {})()
    fight_control_probe.PowerValue = 88.0
    fight_control_probe.PhysicalValue = 5.0
    fight_control_probe.PhysicalValue_MAX = 120.0
    fight_control_probe.SwordSoulValue = 100.0
    fight_control_probe.StiffStack = 42.0
    fight_control_probe.StiffProtectState = True
    fight_control_probe.CanOutControl = False
    fight_control_probe.reset_count = 0
    fight_control_probe.ResetCombatOperation = lambda: setattr(
        fight_control_probe, "reset_count", fight_control_probe.reset_count + 1
    )
    fight_control_probe.getFightStateMachine = lambda: fight_state_machine
    ensure_resources.__globals__["GetComponent"] = lambda name: fight_control_probe
    ensure_resources(object(), {
        "reset_combat_resources": True,
        "ensure_sword_soul": True,
        "sword_soul_value": 50.0,
    })
    assert fight_control_probe.reset_count == 1
    assert fight_state_machine.state == "fight_none"
    assert fight_control_probe.PowerValue == 0.0
    assert fight_control_probe.PhysicalValue == 120.0
    assert fight_control_probe.SwordSoulValue == 50.0
    assert fight_control_probe.StiffStack == 0.0
    assert fight_control_probe.StiffProtectState is False
    assert fight_control_probe.CanOutControl is True

    tutorial_ui = json.loads(source(RESOURCE / "ui/TutorialScreen.json"))
    control_ui = json.loads(source(RESOURCE / "ui/Control.json"))
    ui_text = json.dumps(tutorial_ui, ensure_ascii=False)
    control_text = json.dumps(control_ui, ensure_ascii=False)
    for name in ("StageGuide", "WindowCue", "PressedGlow", '"Progress@common.progress_bar"', "guide_stage"):
        require(ui_text, name)
    guide_children = {
        name.split("@", 1)[0]: value
        for entry in tutorial_ui["guide_overlay"]["controls"]
        for name, value in entry.items()
    }
    assert_alpha_chain(guide_children["StageGuide"], "guide_overlay/StageGuide")
    assert_alpha_chain(guide_children["WindowCue"], "guide_overlay/WindowCue")
    assert_alpha_chain(tutorial_ui["guide_stage"], "guide_stage")
    require(control_text, "TutorialFocus")
    require(control_text, "↓ 这里是怒气")

    moves = next(chapter for chapter in load_catalog() if chapter["id"] == "moves")
    pages = [page for section in moves["sections"] for page in section["pages"]]
    pages_by_id = {page["id"]: page for page in pages}
    assert len(pages) == 14
    assert all(page["practice"].get("training") == {"arena": True, "dummy": True} for page in pages)
    assert all(page["practice"]["pacing"]["enabled"] is True for page in pages)
    assert sum(bool(step.get("dummy_cue")) for page in pages for step in page["practice"]["steps"]) >= 6
    assert all(len(step.get("stages", [])) <= 4 for page in pages for step in page["practice"]["steps"])
    charge_pages = [page for page in pages if page["id"].startswith("charge_")]
    assert len(charge_pages) == 3
    assert all(
        step.get("reset_combat_resources") is True
        for page in charge_pages
        for step in page["practice"]["steps"]
    )
    assert all(
        step.get("sword_soul_value") in (50.0, 100.0)
        for page in charge_pages
        for step in page["practice"]["steps"]
    )
    special_steps = pages_by_id["special_training"]["practice"]["steps"]
    ultimate_steps = pages_by_id["special_ultimate"]["practice"]["steps"]
    assert special_steps[0]["focus"] == "power"
    assert special_steps[1]["ensure_power"] and special_steps[1]["power_for"] == "skill"
    assert ultimate_steps[0]["skip_if_no_cooldown"]
    assert ultimate_steps[1]["ensure_power"] and ultimate_steps[1]["power_for"] == "super_skill"
    for text in visible_strings(moves):
        assert not re.search(r"[A-Za-z_]", text), "player-facing English/technical text: %r" % text

    print("tutorial training regression: PASS")


if __name__ == "__main__":
    main()
