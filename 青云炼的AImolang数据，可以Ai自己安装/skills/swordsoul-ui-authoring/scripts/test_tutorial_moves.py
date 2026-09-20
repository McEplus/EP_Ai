#!/usr/bin/env python3
"""招式教学目录、真实 SWS 状态桥与实机判定回归。"""

from __future__ import print_function

import ast
import runpy
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
UI_DIR = ROOT / "src/SwordSoul_NewERA_B/SwordSoulFightScripts/UISystem"
FIGHT_DIR = ROOT / "src/SwordSoul_NewERA_B/SwordSoulFightScripts/FightSystem"
RESOURCE_DIR = ROOT / "src/SwordSoul_NewERA_R"


def require(source, snippet):
    assert snippet in source, "missing move tutorial contract: %s" % snippet


def load_catalog():
    path = UI_DIR / "TutorialCatalog.py"
    return runpy.run_path(str(path))["TUTORIAL_CATALOG"]


def assert_texture(texture):
    assert any(
        (RESOURCE_DIR / (texture + extension)).is_file()
        for extension in (".png", ".tga")
    ), texture


def main():
    catalog = load_catalog()
    moves = next(chapter for chapter in catalog if chapter["id"] == "moves")
    assert [section["id"] for section in moves["sections"]] == [
        "guard", "movement", "variants", "charge", "special"
    ]
    expected_route = {
        "guard": ["guard_training", "guard_perfect"],
        "movement": ["movement_training", "movement_air", "movement_perfect", "movement_cancels"],
        "variants": ["variants_vertical", "variants_mobility", "variants_counter"],
        "charge": ["charge_training", "charge_air", "charge_chase"],
        "special": ["special_training", "special_ultimate"],
    }
    for section in moves["sections"]:
        assert [page["id"] for page in section["pages"]] == expected_route[section["id"]]
    pages = [page for section in moves["sections"] for page in section["pages"]]
    pages_by_id = {page["id"]: page for page in pages}
    assert len(pages) == 14
    assert sum(len(page["practice"]["steps"]) for page in pages) == 29

    for page in pages:
        assert page.get("track", True) is True, page["id"]
        assert page.get("illustration", {}).get("caption"), page["id"]
        assert_texture(page["illustration"]["texture"])
        assert page["practice"]["surface"] == "Control", page["id"]
        assert page["practice"]["pacing"]["enabled"] is True, page["id"]
        for step in page["practice"]["steps"]:
            for key in ("title", "instruction", "hint", "action", "success", "retry", "icon"):
                assert step.get(key), (page["id"], key)
            assert_texture(step["icon"])
            if step["action"] in ("fight_state", "fight_hit"):
                assert step.get("state_ids") or step.get("state_prefixes"), (page["id"], step["title"])
            if step["action"] == "fight_result":
                assert step.get("result_ids"), (page["id"], step["title"])
            assert step.get("phase") == "演示后实操", (page["id"], step["title"])
            assert step.get("read_time") == 0.0, (page["id"], step["title"])
            assert step.get("demo", {}).get("repeat") == 2, (page["id"], step["title"])
            assert not step.get("demo_only", False), (page["id"], step["title"])

    guard = pages_by_id["guard_perfect"]
    assert [step["action"] for step in guard["practice"]["steps"]] == [
        "fight_state", "fight_result", "fight_result"
    ]
    assert guard["practice"]["steps"][1]["result_ids"] == ["common_defense"]
    assert guard["practice"]["steps"][2]["result_ids"] == ["perfect_defense"]

    movement = pages_by_id["movement_training"]
    assert [step["action"] for step in movement["practice"]["steps"]] == [
        "dodge_up", "fight_state"
    ]
    first_dodge = movement["practice"]["steps"][0]
    second_dodge = movement["practice"]["steps"][1]
    assert first_dodge["require_stage_completion"] is True
    assert first_dodge["fail_state_ids"] == second_dodge["state_ids"]
    assert [stage["action"] for stage in first_dodge["stages"]] == ["dodge_down", "fight_state", "dodge_up"]
    assert first_dodge["stages"][1]["state_ids"] == [
        "fight_dodge_forward", "fight_dodge_back", "fight_dodge_left", "fight_dodge_right"
    ]
    assert second_dodge["state_ids"] == [
        "fight_dodge_forward_second", "fight_dodge_back_second",
        "fight_dodge_left_second", "fight_dodge_right_second"
    ]
    assert second_dodge["hold_action"] == "dodge_down"
    assert second_dodge["hold_release_action"] == "dodge_up"
    assert second_dodge["hold_duration"] == 0.5
    assert first_dodge["ensure_physical"] and second_dodge["ensure_physical"]
    variant_steps = [
        step for page_id in ("variants_vertical", "variants_mobility", "variants_counter")
        for step in pages_by_id[page_id]["practice"]["steps"]
    ]
    assert all(step["action"] == "fight_hit" for step in variant_steps)
    assert sorted(set(step["state_ids"][0] for step in variant_steps)) == sorted([
        "fight_attack_sprint", "fight_attack_up", "fight_attack_jump",
        "fight_attack_fly", "fight_attack_chase", "fight_attack_step",
        "fight_attack_execute"
    ])
    charge_steps = [
        step for page_id in ("charge_training", "charge_air", "charge_chase")
        for step in pages_by_id[page_id]["practice"]["steps"]
    ]
    assert sorted(set(step["state_ids"][0] for step in charge_steps)) == sorted([
        "fight_attack_sneaking_1", "fight_attack_sneaking_2",
        "fight_attack_sneaking_3", "fight_attack_sneaking_4",
        "fight_attack_sneaking_5"
    ])
    assert all(
        "fight_sneaking" in step.get("silent_state_ids", [])
        for step in charge_steps
    )
    cancel_steps = pages_by_id["movement_cancels"]["practice"]["steps"]
    assert cancel_steps[0]["silent_state_ids"] == ["fight_attack_first"]
    assert all(
        step.get("silent_state_prefixes") == ["fight_dodge_", "fight_budge_"]
        for step in cancel_steps[1:]
    )
    assert all(step["silent_state_prefixes"] == ["fight_budge_"] for step in pages_by_id["charge_chase"]["practice"]["steps"])
    special_training = pages_by_id["special_training"]["practice"]["steps"]
    special_ultimate = pages_by_id["special_ultimate"]["practice"]["steps"]
    assert [step["action"] for step in special_training] == ["fight_hit", "fight_state"]
    assert [step["action"] for step in special_ultimate] == ["fight_input_rejected", "fight_state"]
    assert special_training[0]["focus"] == "power"
    assert special_training[1]["power_for"] == "skill"
    assert special_ultimate[0]["skip_if_no_cooldown"] is True
    assert special_ultimate[1]["power_for"] == "super_skill"
    assert all(page["practice"].get("training", {}).get("arena") for page in pages)
    assert all(len(step.get("stages", [])) <= 4 for page in pages for step in page["practice"]["steps"])

    controllers_source = (FIGHT_DIR / "Controllers.py").read_text(encoding="utf-8")
    fight_source = (FIGHT_DIR / "FightClient.py").read_text(encoding="utf-8")
    condition_source = (FIGHT_DIR / "Condition.py").read_text(encoding="utf-8")
    practice_source = (UI_DIR / "TutorialPractice.py").read_text(encoding="utf-8")
    catalog_source = (UI_DIR / "TutorialCatalog.py").read_text(encoding="utf-8")

    for page in pages:
        for step in page["practice"]["steps"]:
            for state_id in step.get("state_ids", []):
                require(controllers_source, '"%s"' % state_id.replace("fight_", "", 1))

    state_start = controllers_source.index("FightStateObj.onStart()")
    notify_start = controllers_source.index("TutorialPracticeSystem.OnFightStateEntered(self.StateId)")
    assert state_start < notify_start

    for snippet in (
        'NotifyTutorialFightResult("common_defense")',
        'NotifyTutorialFightResult("perfect_defense"',
        'NotifyTutorialFightResult("perfect_dodge"',
        'NotifyTutorialFightResult("step")',
        'NotifyTutorialFightResult("hit_heavy")',
        "TutorialPracticeSystem.OnFightHit(",
        'NotifyTutorialFightInputRejected("skill", "cooldown")',
        'NotifyTutorialFightInputRejected("super_skill", "cooldown")',
        "self.DodgeLevel = 2",
        "CreateTimer(0.5, func, False)",
    ):
        require(fight_source, snippet)
    for state_name in ("Forward", "Back", "Left", "Right"):
        require(condition_source, "class ToDodge%sSecond" % state_name)
    require(condition_source, "FightControlSystemObj.DodgeLevel == 2")

    for snippet in (
        "def _matchesStep(self, Step, Action, Value=None):",
        "def OnFightStateEntered(self, StateId):",
        "def OnFightResult(self, ResultId, Data=None):",
        "def OnFightHit(self, StateId, TargetId=None, Damage=0.0, AttackLevel=0.0):",
        "def OnFightInputRejected(self, InputType, Reason, Data=None):",
        'Action == "fight_state" and Step.get("action") != "fight_state"',
        'SilentStateId in Step.get("silent_state_ids", [])',
        "def _updateHoldPrompt(self, Step, Action):",
        'Step.get("require_stage_completion", False)',
        'Step.get("fail_state_ids", [])',
    ):
        require(practice_source, snippet)

    hit_scope = fight_source.index("if AttackId == playerId:", fight_source.index("def OnHitDamage"))
    hit_notify = fight_source.index("TutorialPracticeSystem.OnFightHit(", hit_scope)
    next_method = fight_source.index("\n    def ShowDamage", hit_scope)
    assert hit_scope < hit_notify < next_method
    require(fight_source, 'DestroyTimer(TimerManager.getTimer("SuperSkillRejectTimer"))')

    assert "内容制作中" not in catalog_source[catalog_source.index('"id": "moves"'):catalog_source.index('"id": "mechanics"')]
    print("tutorial move chapter regression: PASS")


if __name__ == "__main__":
    main()
