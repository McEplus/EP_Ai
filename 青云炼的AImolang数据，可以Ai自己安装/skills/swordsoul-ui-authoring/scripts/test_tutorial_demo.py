#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""教程真实状态机预演、输入锁与双方复位回归。"""

from __future__ import print_function

import ast
import runpy
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
FIGHT = ROOT / "src/SwordSoul_NewERA_B/SwordSoulFightScripts"
CATALOG_PATH = FIGHT / "UISystem/TutorialCatalog.py"
PRACTICE_PATH = FIGHT / "UISystem/TutorialPractice.py"
CONTROL_PATH = FIGHT / "UISystem/Control.py"
TRAINING_PATH = FIGHT / "TutorialTrainingServer.py"
CONTROLLERS_PATH = FIGHT / "FightSystem/Controllers.py"


def load_runtime_method(path, class_name, method_name):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    source_class = next(
        node for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == class_name
    )
    method = next(
        node for node in source_class.body
        if isinstance(node, ast.FunctionDef) and node.name == method_name
    )
    method.decorator_list = []
    runtime_class = ast.ClassDef(
        name="RuntimeProbe",
        bases=[],
        keywords=[],
        body=[method],
        decorator_list=[],
    )
    namespace = {}
    module = ast.Module(body=[runtime_class], type_ignores=[])
    exec(compile(ast.fix_missing_locations(module), str(path), "exec"), namespace)
    return getattr(namespace["RuntimeProbe"], method_name)


def main():
    catalog = runpy.run_path(str(CATALOG_PATH))["TUTORIAL_CATALOG"]
    steps = [
        step
        for chapter in catalog[1:]
        for section in chapter["sections"]
        for page in section["pages"]
        for step in page["practice"]["steps"]
    ]
    demos = [step["demo"] for step in steps if step.get("demo")]
    assert len(steps) == 47
    assert len(demos) == 47
    assert all(step.get("phase") != "自己做" for step in steps)
    assert all(demo.get("repeat") == 2 for demo in demos)
    assert all(demo.get("text") and 1.5 <= demo.get("duration", 0) <= 6.0 for demo in demos)

    pages = {
        page["id"]: page
        for chapter in catalog
        for section in chapter["sections"]
        for page in section["pages"]
    }
    armor_hold_states = pages["armor_training"]["practice"]["steps"][1]["demo"]["player_states"]
    assert armor_hold_states == [{"at": 0.0, "state_id": "fight_sneaking"}]
    armor_clash_states = pages["armor_clash"]["practice"]["steps"][1]["demo"]["player_states"]
    assert armor_clash_states == [
        {"at": 0.0, "state_id": "fight_sneaking"},
        {"at": 0.55, "state_id": "fight_attack_sneaking_1"},
    ]
    interrupt_states = pages["armor_interrupt"]["practice"]["steps"][0]["demo"]["player_states"]
    assert interrupt_states == [{"at": 0.55, "state_id": "fight_attack_first"}]
    down_states = pages["stiff_heavy"]["practice"]["steps"][0]["demo"]["player_states"]
    assert down_states == [{"at": 0.0, "state_id": "fight_try_defense"}]

    # Codex 2026-07-24: 关键派生招式必须由真实输入链形成，禁止把结果状态直接塞进播放器。
    authentic_demo_contracts = {
        ("movement_air", 0): (["jump", "jump"], ["fight_second_jump_forward"]),
        ("movement_air", 1): (["jump"], ["fight_step"]),
        ("variants_vertical", 1): (["jump", "jump", "attack_down", "attack_up"], ["fight_attack_jump"]),
        ("variants_mobility", 1): (["hook_down", "hook_up", "attack_down", "attack_up"], ["fight_attack_fly"]),
        ("guard_perfect", 2): (["defense_down", "defense_up"], ["fight_perfect_defense"]),
        ("variants_counter", 2): (["defense_down", "defense_up", "attack_down", "attack_up"], ["fight_perfect_defense", "fight_attack_execute"]),
        ("armor_invincible", 0): (["defense_down", "defense_up", "attack_down", "attack_up"], ["fight_perfect_defense", "fight_attack_execute"]),
        ("charge_air", 0): (["jump", "jump", "attack_down", "attack_up"], ["fight_attack_sneaking_3"]),
        ("charge_air", 1): (["jump", "jump", "attack_down", "attack_up"], ["fight_attack_sneaking_4"]),
    }
    for (page_id, step_index), (actions, required_states) in authentic_demo_contracts.items():
        demo = pages[page_id]["practice"]["steps"][step_index]["demo"]
        assert demo["player_states"] == [], (page_id, step_index)
        assert [entry["action"] for entry in demo["player_actions"]] == actions
        assert all(state_id in demo["required_state_ids"] for state_id in required_states)

    perfect_guard_demo = pages["guard_perfect"]["practice"]["steps"][2]["demo"]
    assert perfect_guard_demo["player_actions"][0] == {"at": 0.94, "action": "defense_down"}

    # Codex 2026-07-26: 每处完美格挡练习都必须把0.3秒门槛写进步骤、提示、失败说明和演示文案。
    for page_id, step_index in (("guard_perfect", 2), ("variants_counter", 2), ("armor_invincible", 0)):
        page = pages[page_id]
        step = page["practice"]["steps"][step_index]
        for field in ("instruction", "hint", "retry"):
            assert "0.3 秒" in step[field], (page_id, field)
        assert "0.3 秒" in step["dummy_cue"]["prompt"], page_id
        assert "0.3 秒" in step["demo"]["text"], page_id
        assert any("0.3 秒" in detail for detail in page["details"]), page_id

    # Codex 2026-07-26: 完美闪避的全部玩家提示必须明确按键后的0.1秒命中窗口。
    perfect_dodge_page = pages["movement_perfect"]
    perfect_dodge_step = perfect_dodge_page["practice"]["steps"][0]
    for field in ("instruction", "hint", "retry"):
        assert "0.1 秒" in perfect_dodge_step[field], field
    assert "0.1 秒" in perfect_dodge_step["dummy_cue"]["prompt"]
    assert "0.1 秒" in perfect_dodge_step["demo"]["text"]
    assert any("0.1 秒" in detail for detail in perfect_dodge_page["details"])

    # Codex 2026-07-26: 两处完美弹反都只能在真实格挡结果返回后排入反击按键，不能按绝对时间直接调用结果状态。
    for page_id, step_index in (("variants_counter", 2), ("armor_invincible", 0)):
        demo = pages[page_id]["practice"]["steps"][step_index]["demo"]
        assert demo["duration"] == 5.6
        assert demo["player_states"] == []
        assert demo["wait_for_state_exit_ids"] == ["fight_attack_execute"]
        assert demo["player_actions"][0] == {"at": 0.94, "action": "defense_down"}
        assert [entry.get("after_result") for entry in demo["player_actions"][1:]] == ["perfect_defense"] * 3
        assert [entry["delay"] for entry in demo["player_actions"][1:]] == [0.06, 0.12, 0.30]

    cancel_attack_at = pages["movement_cancels"]["practice"]["steps"][1]["demo"]["player_actions"][2]["at"]
    cancel_defense_at = pages["movement_cancels"]["practice"]["steps"][2]["demo"]["player_actions"][2]["at"]
    assert cancel_attack_at == 0.45 and cancel_defense_at == 0.45
    rage_step = pages["special_training"]["practice"]["steps"][0]
    assert rage_step["state_prefixes"] == ["fight_attack_sneaking_"]
    assert "普通攻击不会增加怒气" in rage_step["hint"]

    controllers_source = CONTROLLERS_PATH.read_text(encoding="utf-8")
    demo_states = [
        state["state_id"]
        for demo in demos
        for state in demo.get("player_states", [])
    ]
    assert demo_states
    assert all(state_id.startswith("fight_") for state_id in demo_states)
    for state_id in set(demo_states):
        short_id = state_id.replace("fight_", "", 1)
        assert '"%s"' % short_id in controllers_source, state_id

    practice_source = PRACTICE_PATH.read_text(encoding="utf-8")
    control_source = CONTROL_PATH.read_text(encoding="utf-8")
    training_source = TRAINING_PATH.read_text(encoding="utf-8")
    for snippet in (
        "def _startStepDemo(self, Step, Token, StepIndex, DemoOverride=None, PassIndex=1):",
        "def _playDemoState(self, Token, StepIndex, StateId):",
        "def _playDemoAction(self, Token, StepIndex, ActionData):",
        "def _queueDemoResultActions(self, ResultId):",
        "def _performDemoJump(self, FightControlSystem):",
        "def _enterDemoPlayerRoot(self):",
        'StateMachine.GetStateMachine("RootAnimationStateMachine")',
        'RootAnimationStateMachine.SetState("root_fight")',
        "def _restoreDemoPlayerRoot(self):",
        "FightStateMachine.SetState(StateId)",
        "RunningStateObj.State_Attack = True",
        "RunningStateObj.State_Block = False",
        'CallServer("PreviewTutorialTrainingStep"',
        'CallServer("FinishTutorialTrainingPreview"',
        "ClientApi.Control.Control.SetCanAll(not Locked)",
        "self._setDemoInputLocked(False)",
        "def _saveDemoResources(self):",
        "def _restoreDemoResources(self):",
        "def _applyDemoStateControl(self, FightControlSystem, StateId):",
        "def _recordStepFailure(self, Step):",
        "self.StepFailureCount < 4",
        'ReplayDemo["repeat"] = 1',
        'elif PlayedStateCount < ExpectedStateCount:',
        'getattr(self, "LastFightStateId", "fight_none") in WaitStateIds',
        "self._startStepDemo(Step, self.SessionToken, self.StepIndex, ReplayDemo)",
    ):
        assert snippet in practice_source, snippet
    assert "StateMachine.AnimationStateMachine" not in practice_source
    assert 'if ActionData.get("after_result", ""):' in practice_source
    assert practice_source.index("self._setDemoInputLocked(False)") < practice_source.index("self._requestStepScene(Step)")
    cancel_source = practice_source[
        practice_source.index("def Cancel(self, ShowMessage=True):"):
        practice_source.index("def DestroyComponent", practice_source.index("def Cancel(self, ShowMessage=True):"))
    ]
    assert cancel_source.index("self._setDemoInputLocked(False)") < cancel_source.index('CallServer("EndTutorialTraining"')
    assert "TutorialPracticeSystem.IsInputLocked()" in control_source

    enter_root = load_runtime_method(
        PRACTICE_PATH,
        "TutorialPracticeSystem",
        "_enterDemoPlayerRoot",
    )
    restore_root = load_runtime_method(
        PRACTICE_PATH,
        "TutorialPracticeSystem",
        "_restoreDemoPlayerRoot",
    )
    root_calls = []
    root_machine = type("RootMachineProbe", (), {
        "SetState": lambda self, state_id: root_calls.append(state_id)
    })()
    state_machine_type = type("StateMachineProbe", (), {
        "GetStateMachine": staticmethod(lambda state_machine_id: root_machine)
    })
    player_root = type("PlayerRootProbe", (), {"StateMachineModel": "native"})()
    for method in (enter_root, restore_root):
        method.__globals__["StateMachine"] = state_machine_type
        method.__globals__["GetComponent"] = lambda name: player_root
    root_probe = type("DemoRootProbe", (), {})()
    root_probe.DemoOriginalStateMachineModel = None
    assert enter_root(root_probe) is True
    assert player_root.StateMachineModel == "fight"
    assert root_calls == ["root_fight"]
    restore_root(root_probe)
    assert player_root.StateMachineModel == "native"
    assert root_calls == ["root_fight", "root_native"]
    assert root_probe.DemoOriginalStateMachineModel is None

    apply_control = load_runtime_method(
        PRACTICE_PATH,
        "TutorialPracticeSystem",
        "_applyDemoStateControl",
    )
    control_probe = type("ControlProbe", (), {
        "AttackState": "none",
        "SneakingAttackState": 0,
        "CommonAttackState": None,
        "ReadyAttack": False,
        "DefenseState": False,
        "DefenseType": "none",
    })()
    apply_control(root_probe, control_probe, "fight_sneaking")
    assert (control_probe.AttackState, control_probe.ReadyAttack) == ("sneaking", True)
    apply_control(root_probe, control_probe, "fight_attack_sneaking_1")
    assert (control_probe.AttackState, control_probe.SneakingAttackState) == ("sneaking_attack", 1)
    apply_control(root_probe, control_probe, "fight_attack_first")
    assert (control_probe.AttackState, control_probe.CommonAttackState) == ("common_attack", 1)
    apply_control(root_probe, control_probe, "fight_try_defense")
    assert control_probe.DefenseState is True

    for snippet in (
        "def PreviewTutorialTrainingStep(self, Args):",
        "def FinishTutorialTrainingPreview(self, Args):",
        "def _getPreviewMovePlan(self, Cue):",
        "self._resetPreviewActors(Session, PlayerId, \"tutorial_preview\")",
        "self._resetPreviewActors(Session, PlayerId, \"tutorial_preview_end\")",
        "def _restorePreviewHealth(self, Session, PlayerId):",
        'Session["preview_health"]',
        "Mob.execute_fight_state",
    ):
        assert snippet in training_source, snippet

    get_plan = load_runtime_method(
        TRAINING_PATH,
        "TutorialTrainingServerSystem",
        "_getPreviewMovePlan",
    )
    get_plan.__globals__["TUTORIAL_REAL_MOVES"] = {
        "reaction": {}, "clash_low": {}, "armor_low": {}, "light": {}, "heavy": {}, "vertigo": {}, "control": {}
    }
    probe = type("PlanProbe", (), {})()
    assert get_plan(probe, {"type": "attack"})[0] == [(0.55, "reaction")]
    assert get_plan(probe, {"type": "attack_clash"})[0] == [(0.55, "clash_low")]
    assert get_plan(probe, {"type": "heavy"})[0] == [(0.65, "heavy")]
    assert get_plan(probe, {"type": "stiff_protect"})[0] == [(0.45, "light"), (1.9, "light")]
    sequence, duration = get_plan(probe, {
        "type": "scripted_sequence",
        "profiles": ["light", "vertigo"],
        "interval": 0.6,
    })
    assert sequence == [(0.45, "light"), (1.05, "vertigo")]
    assert duration > sequence[-1][0]
    assert get_plan(probe, {"type": "scripted_attack", "profile": "missing"})[0] is None

    restore_resources = load_runtime_method(
        PRACTICE_PATH,
        "TutorialPracticeSystem",
        "_restoreDemoResources",
    )
    resource_target = type("ResourceTarget", (), {
        "PowerValue": 1.0,
        "PhysicalValue": 2.0,
        "StiffStack": 3.0,
        "CommonAttackState": 3,
    })()
    resource_probe = type("ResourceProbe", (), {})()
    resource_probe.DemoResourceSnapshot = {
        "PowerValue": 20.0,
        "PhysicalValue": 40.0,
        "StiffStack": 0.0,
        "CommonAttackState": None,
    }
    restore_resources.__globals__["GetComponent"] = lambda name: resource_target
    restore_resources(resource_probe)
    assert (resource_target.PowerValue, resource_target.PhysicalValue, resource_target.StiffStack) == (20.0, 40.0, 0.0)
    assert resource_target.CommonAttackState is None
    assert resource_probe.DemoResourceSnapshot == {}

    queue_result_actions = load_runtime_method(
        PRACTICE_PATH,
        "TutorialPracticeSystem",
        "_queueDemoResultActions",
    )
    queued_actions = []

    def create_result_timer(delay, callback, repeat, *args):
        queued_actions.append((delay, callback, args))
        return "result_timer_%d" % len(queued_actions)

    queue_result_actions.__globals__["CreateTimer"] = create_result_timer
    result_probe = type("ResultActionProbe", (), {})()
    result_probe.DemoActive = True
    result_probe.DemoCurrentData = {
        "player_actions": [
            {"at": 0.94, "action": "defense_down"},
            {"after_result": "perfect_defense", "delay": 0.06, "action": "defense_up"},
            {"after_result": "perfect_defense", "delay": 0.12, "action": "attack_down"},
            {"after_result": "perfect_defense", "delay": 0.30, "action": "attack_up"},
        ]
    }
    result_probe.SessionToken = 5
    result_probe.StepIndex = 2
    result_probe.DemoTriggeredActionKeys = set()
    result_probe.DemoTimers = []
    result_probe._playDemoAction = lambda *args: None
    queue_result_actions(result_probe, "perfect_defense")
    assert [entry[0] for entry in queued_actions] == [0.06, 0.12, 0.30]
    assert [entry[2][-1]["action"] for entry in queued_actions] == ["defense_up", "attack_down", "attack_up"]
    assert len(result_probe.DemoTimers) == 3
    queue_result_actions(result_probe, "perfect_defense")
    assert len(queued_actions) == 3

    record_failure = load_runtime_method(
        PRACTICE_PATH,
        "TutorialPracticeSystem",
        "_recordStepFailure",
    )
    failure_times = iter((1.0, 2.0, 3.0, 4.0))
    record_failure.__globals__["time"] = type("TimeProbe", (), {"time": staticmethod(lambda: next(failure_times))})
    record_failure.__globals__["DestroyTimer"] = lambda timer: None
    failure_probe = type("FailureProbe", (), {})()
    failure_probe.StepFailureIndex = 2
    failure_probe.StepIndex = 2
    failure_probe.StepFailureCount = 0
    failure_probe.LastStepFailureAt = 0.0
    failure_probe.CueRetryTimer = None
    failure_probe.SessionToken = 8
    failure_probe.StageIndex = 3
    failure_probe._findFailureDemo = lambda step: {"text": "再看一次"}
    failure_probe._stopStepReadTimer = lambda: None
    failure_probe._stopDemoPlayback = lambda reset: None
    failure_probe.Render = lambda: None
    replayed = []
    failure_probe._startStepDemo = lambda step, token, index, demo: replayed.append((step, token, index, demo))
    failure_step = {"action": "fight_state"}
    assert [record_failure(failure_probe, failure_step) for _ in range(3)] == [False, False, False]
    assert record_failure(failure_probe, failure_step) is True
    assert replayed == [(failure_step, 8, 2, {"text": "再看一次", "repeat": 1})]
    assert failure_probe.StepFailureCount == 0 and failure_probe.StageIndex == 0

    # Codex 2026-07-24: 首遍结束必须排队第二遍，第二遍结束后才进入实操或机制完成分支。
    finish_demo = load_runtime_method(
        PRACTICE_PATH,
        "TutorialPracticeSystem",
        "_finishStepDemo",
    )
    timer_calls = []
    finish_calls = []
    finish_demo.__globals__["ClientMod"] = type("ClientModProbe", (), {"playerId": "player"})
    finish_demo.__globals__["CallServer"] = lambda name, data: finish_calls.append((name, data))

    def create_demo_timer(delay, callback, repeat, *args):
        timer_calls.append((delay, callback, args))
        return "demo_timer"

    finish_demo.__globals__["CreateTimer"] = create_demo_timer
    demo_probe = type("DemoProbe", (), {})()
    demo_probe.SessionToken = 11
    demo_probe.StepIndex = 3
    demo_probe.ActivePageId = "movement_training"
    demo_probe.DemoExpectedStateCount = 1
    demo_probe.DemoPlayedStateCount = 1
    demo_probe.DemoDummyMoveCount = 0
    demo_probe.DemoPassIndex = 1
    demo_probe.DemoPassTotal = 2
    demo_probe.DemoCurrentData = {"text": "闪避演示", "repeat": 2}
    demo_probe.DemoObservedStates = set()
    demo_probe._stopDemoPlayback = lambda reset: None
    demo_probe.Render = lambda: None
    demo_probe._showWindowCue = lambda text, duration: None
    demo_probe._getStep = lambda: {"title": "一段闪"}
    started_passes = []
    demo_probe._startStepDemo = lambda *args: started_passes.append(args)
    continued = []
    demo_probe._continueAfterDemoSequence = lambda *args: continued.append(args)
    finish_demo(demo_probe, 11, 3)
    assert timer_calls[-1][0] == 0.65 and timer_calls[-1][2][-1] == 2
    first_timer = timer_calls.pop()
    first_timer[1](*first_timer[2])
    assert started_passes and started_passes[0][-1] == 2
    demo_probe.DemoPassIndex = 2
    finish_demo(demo_probe, 11, 3)
    second_timer = timer_calls.pop()
    second_timer[1](*second_timer[2])
    assert continued == [(11, 3, True)]
    assert len(finish_calls) == 2

    restore_health = load_runtime_method(
        TRAINING_PATH,
        "TutorialTrainingServerSystem",
        "_restorePreviewHealth",
    )
    health_values = []
    attr_probe = type("AttrProbe", (), {
        "SetAttrValue": lambda self, attr_type, value: health_values.append((attr_type, value))
    })()
    restore_health.__globals__["ServerApi"] = type("ServerApiProbe", (), {
        "World": type("WorldProbe", (), {
            "Entity": type("EntityProbe", (), {"IsEntityAlive": staticmethod(lambda entity_id: True)})
        })
    })
    restore_health.__globals__["serverApi"] = type("ApiProbe", (), {
        "GetMinecraftEnum": staticmethod(lambda: type("EnumProbe", (), {
            "AttrType": type("AttrTypeProbe", (), {"HEALTH": "health"})
        }))
    })
    restore_health.__globals__["ServerComp"] = type("CompProbe", (), {
        "CreateAttr": staticmethod(lambda player_id: attr_probe)
    })
    health_session = {"preview_health": 12.0}
    restore_health(type("HealthProbe", (), {})(), health_session, "player")
    assert health_values == [("health", 12.0)]
    assert health_session["preview_health"] is None
    print("tutorial real-state demonstration regression: PASS (47 two-pass demonstrations)")


if __name__ == "__main__":
    main()
