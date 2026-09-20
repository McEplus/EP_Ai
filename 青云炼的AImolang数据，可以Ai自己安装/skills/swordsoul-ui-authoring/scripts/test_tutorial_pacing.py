#!/usr/bin/env python3
"""第二章起点击阅读、双遍演示与单次实操节奏回归。"""

from __future__ import print_function

import ast
import runpy
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
CATALOG_PATH = ROOT / "src/SwordSoul_NewERA_B/SwordSoulFightScripts/UISystem/TutorialCatalog.py"
PRACTICE_PATH = ROOT / "src/SwordSoul_NewERA_B/SwordSoulFightScripts/UISystem/TutorialPractice.py"
TRAINING_PATH = ROOT / "src/SwordSoul_NewERA_B/SwordSoulFightScripts/TutorialTrainingServer.py"


def load_runtime_class(method_names):
    tree = ast.parse(PRACTICE_PATH.read_text(encoding="utf-8"))
    source_class = next(
        node for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "TutorialPracticeSystem"
    )
    methods = [
        node for node in source_class.body
        if isinstance(node, ast.FunctionDef) and node.name in method_names
    ]
    assert len(methods) == len(method_names), method_names
    runtime_class = ast.ClassDef(
        name="PacingProbe",
        bases=[],
        keywords=[],
        body=methods,
        decorator_list=[],
    )
    namespace = {}
    module = ast.Module(body=[runtime_class], type_ignores=[])
    exec(compile(ast.fix_missing_locations(module), str(PRACTICE_PATH), "exec"), namespace)
    return namespace["PacingProbe"]


def main():
    catalog = runpy.run_path(str(CATALOG_PATH))["TUTORIAL_CATALOG"]
    moves = next(chapter for chapter in catalog if chapter["id"] == "moves")
    mechanics = next(chapter for chapter in catalog if chapter["id"] == "mechanics")
    move_pages = [page for section in moves["sections"] for page in section["pages"]]
    mechanic_pages = [page for section in mechanics["sections"] for page in section["pages"]]
    paced_pages = move_pages + mechanic_pages

    assert len(move_pages) == 14
    assert len(mechanic_pages) == 10
    assert all(len(section["pages"]) >= 2 for section in moves["sections"] + mechanics["sections"])
    assert all(1 <= len(page["practice"]["steps"]) <= 6 for page in paced_pages)
    assert all(len(page["details"]) == 3 for page in paced_pages)
    assert all(page["practice"]["pacing"] == {
        "enabled": True,
        "read_time": 0.0,
        "success_hold": 3.0,
        "finish_hold": 3.2,
        "continue_to_start": True,
    } for page in paced_pages)

    steps = [step for page in paced_pages for step in page["practice"]["steps"]]
    move_steps = [step for page in move_pages for step in page["practice"]["steps"]]
    mechanic_steps = [step for page in mechanic_pages for step in page["practice"]["steps"]]
    assert len(steps) == 47
    assert len(move_steps) == 29 and len(mechanic_steps) == 18
    assert all(step["phase"] == "演示后实操" for step in move_steps)
    assert all(step["phase"] == "双遍演示" and step["demo_only"] for step in mechanic_steps)
    assert all(step["read_time"] == 0.0 for step in steps)
    assert all(step["success_hold"] >= 3.0 for step in steps)
    assert all(step.get("demo", {}).get("repeat") == 2 for step in steps)
    assert all(not step["title"].startswith("再做一次：") for step in steps)
    assert all(step.get("brief_instruction") and step.get("brief_hint") for step in steps)

    practice_source = PRACTICE_PATH.read_text(encoding="utf-8")
    notify_start = practice_source.index("def Notify(self, Action, Value=None):")
    notify_end = practice_source.index("def _completeStep", notify_start)
    notify_source = practice_source[notify_start:notify_end]
    assert notify_source.index("if not self.StepReady:") < notify_source.index("self._updateHoldPrompt")
    for snippet in (
        "self.StepReadTimer = None",
        "def _beginCurrentStep(self, Token, StepIndex):",
        "self.StepReady = False",
        "def ContinueBriefing(self):",
        "self._showStaticWindowCue(u\"先看左侧说明，按下任意键继续\")",
        'def OnTutorialKeyboardInput(self, Args):',
        'KeyBoardType.KEY_ESCAPE',
        "AdvanceDelay = max(3.0, min(6.0, AdvanceDelay))",
        "FinishDelay = max(2.0, min(8.0, FinishDelay))",
    ):
        assert snippet in practice_source, snippet
    assert "ClientMod.clientApi.GetMinecraftEnum().KeyBoardType.KEY_ESCAPE" in practice_source
    assert "ClientApi.GetMinecraftEnum()" not in practice_source

    runtime_class = load_runtime_class([
        "_getPacing", "_isPaced", "_activateCurrentStep", "_beginCurrentStep",
        "_finishStepBriefing", "ContinueBriefing"
    ])
    probe = runtime_class()
    probe.ActivePageId = "movement_training"
    probe.SceneReady = True
    probe.Finishing = False
    probe.SessionToken = 9
    probe.StepIndex = 0
    probe.Practice = {
        "pacing": {"enabled": True, "read_time": 0.0, "continue_to_start": True},
        "steps": [{
            "title": "一段闪",
            "phase": "演示后实操",
            "read_time": 0.0,
            "brief_hint": "看完说明后点击继续",
            "action": "dodge_up",
        }],
    }
    probe.StepReadTimer = None
    probe._stopStepReadTimer = lambda: None
    probe._stopDemoPlayback = lambda reset=True: None
    locks = []
    probe._setDemoInputLocked = lambda locked: locks.append(locked)
    probe._hideWindowCue = lambda: None
    probe._ensureStepResources = lambda step: None
    probe._startMechanicStatus = lambda step: None
    probe._shouldSkipStep = lambda step: False
    probe._completeStep = lambda step, text=None: None
    probe._getStep = lambda: probe.Practice["steps"][probe.StepIndex]
    probe.Render = lambda: None
    windows = []
    probe._showWindowCue = lambda text, duration: windows.append((text, duration))
    probe._showStaticWindowCue = lambda text: windows.append((text, None))
    scene_requests = []
    probe._requestStepScene = lambda step: scene_requests.append(step["title"])
    timers = []

    def create_timer(delay, callback, repeat, *args):
        timers.append((delay, callback, args))
        return "read_timer"

    runtime_class._activateCurrentStep.__globals__["CreateTimer"] = create_timer
    probe._activateCurrentStep()
    assert probe.StepReady is False
    assert probe.WaitingForContinue is True
    assert scene_requests == []
    assert windows == [("先看左侧说明，按下任意键继续", None)]
    assert timers == []
    assert locks == [True]
    probe.ContinueBriefing()
    assert probe.StepReady is True
    assert probe.WaitingForContinue is False
    assert locks == [True, False]
    assert scene_requests == ["一段闪"]

    # Codex 2026-07-21: 成功停留期保持玩家输入开放，至少三秒后才进入下一步。
    completion_class = load_runtime_class(["_getPacing", "_isPaced", "_completeStep"])
    completion = completion_class()
    completion.ActivePageId = "movement_training"
    completion.Practice = {"pacing": {"enabled": True, "success_hold": 3.0}, "steps": [{}]}
    completion.StepIndex = 0
    completion.Advancing = False
    completion.StepReady = True
    completion.StageIndex = 0
    completion.FeedbackText = ""
    completion.FeedbackTimer = None
    completion.PendingAction = None
    completion.SessionToken = 12
    completion._stopStepReadTimer = lambda: None
    completion._hideWindowCue = lambda: None
    completion._showSuccess = lambda step: None
    completion_locks = []
    completion._setDemoInputLocked = lambda locked: completion_locks.append(locked)
    completion_timers = []

    def create_completion_timer(delay, callback, repeat, *args):
        completion_timers.append((delay, callback, args))
        return "success_timer"

    completion_class._completeStep.__globals__["CreateTimer"] = create_completion_timer
    completion._completeStep({"stages": [], "success_hold": 2.0})
    assert completion.Advancing is True
    assert completion.StepReady is True
    assert completion_locks == [False]
    assert completion_timers and completion_timers[0][0] == 3.0
    assert completion.StepIndex == 0
    assert scene_requests == ["一段闪"]

    training_source = TRAINING_PATH.read_text(encoding="utf-8")
    assert 'PageId.startswith("armor_")' in training_source
    assert 'PageId.startswith("stiff_")' in training_source
    print("tutorial click pacing regression: PASS (24 paced pages, 47 paced steps)")


if __name__ == "__main__":
    main()
