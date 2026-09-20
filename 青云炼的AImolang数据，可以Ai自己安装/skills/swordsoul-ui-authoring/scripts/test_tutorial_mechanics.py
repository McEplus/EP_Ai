#!/usr/bin/env python3
"""第三章霸体、僵直、训练木偶与机制状态栏回归。"""

from __future__ import print_function

import ast
import json
import re
import runpy
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
BEHAVIOR = ROOT / "src/SwordSoul_NewERA_B/SwordSoulFightScripts"
RESOURCE = ROOT / "src/SwordSoul_NewERA_R"
UI_DIR = BEHAVIOR / "UISystem"


def source(path):
    return path.read_text(encoding="utf-8-sig")


def require(text, snippet):
    assert snippet in text, "missing mechanics tutorial contract: %s" % snippet


def load_catalog():
    path = UI_DIR / "TutorialCatalog.py"
    return runpy.run_path(str(path))["TUTORIAL_CATALOG"]


def load_functions(path, names):
    namespace = {}
    text = source(path)
    for name in names:
        match = re.search(
            r"(?ms)^def %s\(.*?(?=^def |^@LoadingComponent)" % re.escape(name),
            text,
        )
        assert match, "missing runtime helper: %s" % name
        exec(compile(match.group(0), str(path), "exec"), namespace)
    return [namespace[name] for name in names]


def load_runtime_methods(path, class_name, names):
    tree = ast.parse(source(path))
    class_node = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == class_name)
    methods = [
        node for node in class_node.body
        if isinstance(node, ast.FunctionDef) and node.name in names
    ]
    assert len(methods) == len(names), "missing runtime methods: %s" % names
    runtime_class = ast.ClassDef(
        name="RuntimePracticeProbe",
        bases=[],
        keywords=[],
        body=methods,
        decorator_list=[],
    )
    namespace = {}
    module = ast.Module(body=[runtime_class], type_ignores=[])
    exec(compile(ast.fix_missing_locations(module), str(path), "exec"), namespace)
    return namespace["RuntimePracticeProbe"]


def assert_texture(texture):
    assert any((RESOURCE / (texture + extension)).is_file() for extension in (".png", ".tga")), texture


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
    children = control.get("controls", []) if isinstance(control, dict) else []
    if children:
        assert control.get("propagate_alpha") is True, "broken mechanics alpha chain: %s" % path
    for entry in children:
        for name, child in entry.items():
            assert_alpha_chain(child, path + "/" + name.split("@", 1)[0])


def main():
    catalog = load_catalog()
    mechanics = next(chapter for chapter in catalog if chapter["id"] == "mechanics")
    assert [section["id"] for section in mechanics["sections"]] == ["armor", "stiff"]
    expected_route = {
        "armor": ["armor_training", "armor_clash", "armor_interrupt", "armor_skill", "armor_invincible"],
        "stiff": ["stiff_training", "stiff_air", "stiff_refresh", "stiff_heavy", "stiff_protect"],
    }
    for section in mechanics["sections"]:
        assert [page["id"] for page in section["pages"]] == expected_route[section["id"]]
    pages = [page for section in mechanics["sections"] for page in section["pages"]]
    pages_by_id = {page["id"]: page for page in pages}
    assert len(pages) == 10
    assert sum(len(page["practice"]["steps"]) for page in pages) == 18
    assert all(page.get("track", True) for page in pages)
    assert all(page["practice"]["training"] == {"arena": True, "dummy": True, "mechanics": True} for page in pages)
    assert all(page["practice"]["pacing"]["enabled"] is True for page in pages)
    assert all(len(step.get("stages", [])) <= 4 for page in pages for step in page["practice"]["steps"])
    for page in pages:
        assert_texture(page["illustration"]["texture"])
        for step in page["practice"]["steps"]:
            for key in ("title", "instruction", "hint", "action", "success", "retry", "icon", "mechanic"):
                assert step.get(key), (page["id"], key)
            assert step.get("phase") == "双遍演示"
            assert step.get("read_time") == 0.0
            assert step.get("demo_only") is True
            assert step.get("demo", {}).get("repeat") == 2
            assert_texture(step["icon"])
            for stage in step.get("stages", []):
                assert_texture(stage["icon"])
    for text in visible_strings(mechanics):
        assert not re.search(r"[A-Za-z_]", text), "player-facing English/technical text: %r" % text

    armor_intro = pages_by_id["armor_training"]["practice"]["steps"]
    assert [step["action"] for step in armor_intro] == ["fight_hit", "fight_result"]
    assert armor_intro[-1]["result_ids"] == ["armor_held"]
    armor_clash = pages_by_id["armor_clash"]["practice"]["steps"]
    assert armor_clash[0]["result_ids"] == ["attack_clash"]
    assert armor_clash[1]["previous_state_prefixes"] == ["fight_attack_sneaking_"]
    armor_skill = pages_by_id["armor_skill"]["practice"]["steps"]
    assert armor_skill[0]["result_ids"] == ["armor_held"]
    assert armor_skill[0]["ensure_power"] and armor_skill[0]["power_for"] == "skill"
    assert armor_skill[1]["state_ids"] == ["fight_attack_super_skill"]
    for execute_step in pages_by_id["armor_invincible"]["practice"]["steps"]:
        assert execute_step["action"] == "fight_state"
        assert execute_step["state_ids"] == ["fight_attack_execute"]
        assert len(execute_step["stages"]) == 3
        assert execute_step["stages"][-1]["action"] == "fight_state"
        assert execute_step["stages"][-1]["state_ids"] == ["fight_attack_execute"]

    stiff_ground = pages_by_id["stiff_training"]["practice"]["steps"]
    for combo_step in stiff_ground[1:]:
        assert combo_step["mechanic"] == "stiff_combo"
        assert combo_step["target_training_dummy"] is True
        assert len(combo_step["hit_sequence"]) == 3
        assert combo_step["dummy_cue"]["type"] == "player_combo"
    stiff_air = pages_by_id["stiff_air"]["practice"]["steps"]
    assert stiff_air[0]["hit_sequence"] == [{"state_ids": ["fight_attack_up"]}]
    for combo_step in stiff_air[1:]:
        assert combo_step["hit_sequence"][0]["state_ids"] == ["fight_attack_up"]
        assert len(combo_step["hit_sequence"]) == 3
        assert combo_step["dummy_cue"]["type"] == "player_combo"
    stiff_refresh = pages_by_id["stiff_refresh"]["practice"]["steps"]
    assert [step["result_reasons"] for step in stiff_refresh] == [["vertigo"], ["non_fading"], ["control"]]
    assert pages_by_id["stiff_heavy"]["practice"]["steps"][0]["result_reasons"] == ["heavy"]
    stiff_steps = [step for page_id in expected_route["stiff"] for step in pages_by_id[page_id]["practice"]["steps"]]
    assert all(step.get("reset_stiff_stack") for step in stiff_steps)
    for step in pages_by_id["stiff_protect"]["practice"]["steps"][1:]:
        assert step["ensure_physical"] and step["ensure_out_control"]

    server_source = source(BEHAVIOR / "TutorialTrainingServer.py")
    practice_source = source(UI_DIR / "TutorialPractice.py")
    client_source = source(BEHAVIOR / "FightSystem/FightClient.py")
    controllers_source = source(BEHAVIOR / "FightSystem/Controllers.py")
    reset_reason, tutorial_result = load_functions(
        BEHAVIOR / "FightSystem/FightClient.py",
        ["GetStiffResetReason", "GetStiffTutorialResult"],
    )
    assert reset_reason("fight_hit_light", True, True, False, False) == "space"
    assert reset_reason("fight_hit_light", False, False, False, False) == "non_fading"
    assert reset_reason("fight_hit_space", True, False, True, False) == "vertigo"
    assert reset_reason("fight_hit_space", True, False, True, True) == "control"
    assert tutorial_result("light", 0.29, 0.5, "") == "stiff_accumulated"
    assert tutorial_result("light", 0.30, 0.5, "") == "stiff_ground_limit"
    assert tutorial_result("space", 0.50, 0.5, "") == "stiff_air_limit"
    assert tutorial_result("light", 0.10, 0.5, "vertigo") == "stiff_reset"
    fight_server_source = source(BEHAVIOR / "FightSystem/FightServer.py")
    mob_controller_source = source(ROOT / "src/SwordSoul_NewERA_B/SwordSoulMobFightScripts/Combat/FightController.py")
    mob_entity_source = source(ROOT / "src/SwordSoul_NewERA_B/SwordSoulMobFightScripts/Entities/QingYunMob.py")
    empty_state_source = source(ROOT / "src/SwordSoul_NewERA_B/SwordSoulMobFightScripts/Entities/FightState/UseEmptyState.py")
    pike_state_source = source(ROOT / "src/SwordSoul_NewERA_B/SwordSoulMobFightScripts/Entities/FightState/UsePikeState.py")
    for profile in ("armor_low", "armor_strong", "light", "light_medium", "light_long", "space", "heavy", "vertigo", "control"):
        require(server_source, '"%s": {' % profile)
    for snippet in (
        "def IsMechanicsTrainingPlayer(self, PlayerId):",
        "def _runDummyMove(self, PlayerId, StepToken, MoveName, DummyPos=None):",
        "def _runDummySequenceMove(self, PlayerId, StepToken, MoveName):",
        "self._runDummySequenceMove, False, PlayerId, StepToken, ProfileName",
        "def _stopDummyPersistentMoves(self, DummyId):",
        'ActiveCueTypes = ("attack", "attack_clash", "scripted_attack", "scripted_sequence", "heavy", "stiff_protect", "player_combo")',
        'if CueType == "player_combo":',
        "Mob.command_translator.StiffStack = 0.0",
        "Mob.command_translator.StiffProtectState = False",
        'elif CueType == "scripted_sequence":',
        'Profiles = Cue.get("profiles", []) or []',
        "WindowAt = max(0.1, Delay - WindowLead)",
        "def _runDummyClash(self, PlayerId, StepToken):",
        "TUTORIAL_REAL_MOVES = {",
        'Mob.execute_fight_state(Move["state"]',
        "Mob.set_entity_item(2, ItemData, 0)",
        "Mob.set_hard_switch(True)",
        "Mob.set_weapon_type(Move.get(\"weapon\", \"empty\"), True)",
        "PlayerIntendLeaveServerEvent",
        "SetPlayerGameType(PlayerId, GameType.Survival)",
        "SetPlayerGameType(PlayerId, ReturnGameType)",
        'AttrComp.SetAttrValue(AttrType, MaxHealth)',
        'ServerComp.CreateAttr(PlayerId).SetAttrValue(AttrType, ReturnHealth)',
        "def OnTrainingPlayerActuallyHurt(self, Args):",
        "ServerEvents.EntityEvents.ActuallyHurtServerEvent",
        "MaxSafeDamage = max(0.0, float(CurrentHealth) - 1.0)",
    ):
        require(server_source, snippet)
    assert '"no_damage": True' not in server_source
    assert '"super_attack": True' not in server_source
    assert '"damage":' not in server_source
    assert "HealthChangeBeforeServerEvent" not in server_source
    assert "DamageEvent" not in server_source
    assert 'Args["cancel"]' not in server_source
    assert "Mob.CreateAttack" not in server_source
    assert "fight_tutorial_attack" not in server_source
    assert "ApplyTutorialHit" not in server_source
    assert "fight_tutorial_attack" not in mob_controller_source
    assert "fight_tutorial_attack" not in mob_entity_source
    require(empty_state_source, "class EmptyAttackFirst(BaseFightState):")
    require(empty_state_source, "class EmptyAttackUp(BaseFightState):")
    require(empty_state_source, "class EmptyAttackExecute(BaseFightState):")
    require(empty_state_source, "class EmptyAttackSneaking1(BaseFightState):")
    require(empty_state_source, "class EmptyKingDeterrence(BaseFightState):")
    require(empty_state_source, '"vertigo": True')
    require(empty_state_source, '"qingyun_king_deterrence_attack_timer_%s" % self.Mob.entityId')
    require(pike_state_source, "class PikeAttackExecute(BaseFightState):")
    require(pike_state_source, '"control": True')
    for state_id in ("fight_attack_first", "fight_attack_second", "fight_attack_up", "fight_attack_execute", "fight_attack_sneaking_1", "fight_skill_king_deterrence"):
        require(mob_entity_source, '@BindMobState(QINGYUN_ENTITY_TYPE, "%s"' % state_id)
    require(mob_entity_source, '@BindMobState(QINGYUN_ENTITY_TYPE, "fight_attack_execute", PIKE_WEAPON)')
    clash_source = server_source[
        server_source.index("def _runDummyClash(self, PlayerId, StepToken):"):
        server_source.index("def _trackTimer(self, Session, Timer):")
    ]
    # Codex 2026-07-22: 对撞使用钻石剑普攻，判定窗口练习则使用前摇更长的第十四段普攻。
    require(clash_source, 'self._runDummyMove(PlayerId, StepToken, "clash_low")')
    assert 'CallClient("OnAttackDefense"' not in clash_source
    player_combo_start = server_source.index('if CueType == "player_combo":')
    player_combo_source = server_source[
        player_combo_start:
        server_source.index('if CueType == "attack":', player_combo_start)
    ]
    require(player_combo_source, "return True")
    assert "_runDummy" not in player_combo_source
    assert '"retry"' not in player_combo_source
    for snippet in (
        "def _renderMechanicStatus(self, Surface, Step):",
        "def OnIncomingHit(self, AttackLevel):",
        "self.OriginalPhysicalValue",
        "self.OriginalRuleValues",
        'Step.get("ensure_out_control", False)',
        'Step.get("reset_stiff_stack", False)',
        'Step.get("result_reasons", [])',
        'self.LastStiffChangeData',
        'Mechanic == "stiff_combo"',
        "def _trackHitSequence(self, Step, Action, Value):",
        'Step.get("target_training_dummy", False)',
        'FightControlSystem.CancelSkill = False',
        'Step.get("mechanic") == "stiff" and ResultId.startswith("stiff_")',
    ):
        require(practice_source, snippet)

    runtime_practice = load_runtime_methods(
        UI_DIR / "TutorialPractice.py",
        "TutorialPracticeSystem",
        ["_matchesNamedValue", "_matchesStep", "_matchesHitSequenceEntry", "_trackHitSequence"],
    )
    combo_probe = runtime_practice()
    execute_step = pages_by_id["armor_invincible"]["practice"]["steps"][0]
    assert combo_probe._matchesStep(execute_step, "fight_state", {
        "state_id": "fight_attack_execute", "previous_state_id": "fight_perfect_defense"
    }) is True
    assert combo_probe._matchesStep(execute_step, "fight_state", {
        "state_id": "fight_none", "previous_state_id": "fight_attack_execute"
    }) is False
    combo_probe.TrainingDummyId = "dummy"
    combo_probe.StepHitCount = 0
    combo_probe.LastStepHitAt = 0.0
    combo_probe.LastComboStateId = ""
    combo_probe.StageIndex = 0
    combo_probe.LastMechanicResult = "等待演示"
    combo_probe.FeedbackText = ""
    combo_probe.Render = lambda: None
    combo_probe._showRetry = lambda step, text=None: False
    clock = [1.0]
    runtime_practice._trackHitSequence.__globals__["time"] = type(
        "TimeProbe", (), {"time": staticmethod(lambda: clock[0])}
    )
    combo_step = pages_by_id["stiff_air"]["practice"]["steps"][1]
    assert combo_probe._trackHitSequence(combo_step, "fight_hit", {
        "state_id": "fight_attack_up", "target_id": "other"
    }) is False
    assert combo_probe.StepHitCount == 0
    assert combo_probe._trackHitSequence(combo_step, "fight_hit", {
        "state_id": "fight_attack_up", "target_id": "dummy"
    }) is False
    clock[0] = 1.5
    assert combo_probe._trackHitSequence(combo_step, "fight_hit", {
        "state_id": "fight_attack_first", "target_id": "dummy"
    }) is False
    clock[0] = 2.0
    assert combo_probe._trackHitSequence(combo_step, "fight_hit", {
        "state_id": "fight_attack_second", "target_id": "dummy"
    }) is True
    assert combo_probe.StepHitCount == 3
    combo_probe.StepHitCount = 0
    combo_probe.StageIndex = 0
    clock[0] = 10.0
    combo_probe._trackHitSequence(combo_step, "fight_hit", {
        "state_id": "fight_attack_up", "target_id": "dummy"
    })
    clock[0] = 13.0
    assert combo_probe._trackHitSequence(combo_step, "fight_hit", {
        "state_id": "fight_attack_first", "target_id": "dummy"
    }) is False
    assert combo_probe.StepHitCount == 0
    for snippet in (
        'self.OnFightResult("armor_held"',
        'NotifyTutorialFightResult("attack_clash")',
        'NotifyTutorialFightResult("stiff_protected"',
        'NotifyTutorialFightResult("stiff_protect_start")',
        'NotifyTutorialFightResult("stiff_value"',
        "def GetStiffResetReason(",
        "def GetStiffTutorialResult(",
        "StiffTutorialResult = GetStiffTutorialResult(",
        'NotifyTutorialFightResult("out_control"',
        'NotifyTutorialFightResult("out_control_blocked"',
        "TutorialPracticeSystem.OnIncomingHit(AttackLevel)",
    ):
        require(client_source + practice_source, snippet)
    assert 'FightControlSystem.CancelSkillCd = True' not in practice_source
    require(fight_server_source, "def IsMechanicsTrainingPlayer(self, PlayerId):")
    assert "def ApplyTutorialHit(" not in fight_server_source
    require(fight_server_source, "TrainingClash = self.IsMechanicsTrainingPlayer")
    require(fight_server_source, "and not IsMechanicsTraining")
    require(fight_server_source, "if AttackLevel >= 2.0 or OnHurtLevel >= 2.0")
    require(fight_server_source, "OnHurtFightState.SuperArmor == AttackFightState.AttackLevel == 3.0")
    assert '.get("hit_type") == "heavy"' not in fight_server_source
    skill_armor_source = controllers_source[
        controllers_source.index("class StateAttackSkill(StateMachine.State):"):
        controllers_source.index("class StateAttackSuperSkill(StateMachine.State):")
    ]
    require(skill_armor_source, "updateSuperArmor(3.0)")
    require(skill_armor_source, "updateAttackLevel(3.0)")
    ultimate_armor_source = controllers_source[
        controllers_source.index("class StateAttackSuperSkill(StateMachine.State):"):
        controllers_source.index("class StateTryDefense(StateMachine.State):")
    ]
    require(ultimate_armor_source, "updateSuperArmor(4.0)")
    require(ultimate_armor_source, "updateAttackLevel(4.0)")
    require(ultimate_armor_source, '"state_type": "GodState", "value": True')
    execute_armor_source = controllers_source[
        controllers_source.index("class StateAttackExecute(StateMachine.State):"):
        controllers_source.index("class StateSneaking(StateMachine.State):")
    ]
    require(execute_armor_source, "updateSuperArmor(3.0)")
    require(execute_armor_source, "updateAttackLevel(3.0)")
    require(execute_armor_source, '"state_type": "GodState", "value": True')
    # Codex 2026-07-20: 完美格挡先提供3秒无敌；提前反击要切换为动作全程无敌，并在退出时关闭。
    perfect_defense_source = client_source[
        client_source.index("    def UpdatePerfectDefenseState(self, State):"):
        client_source.index("    def OnPerfectDodge(self, AutoPerfectDodge):")
    ]
    require(perfect_defense_source, '"state_type": "GodState", "value": True')
    require(perfect_defense_source, "CreateTimer(3.0, EndPerfectDefenseState, False)")
    assert execute_armor_source.index("UpdatePerfectDefenseState(False)") < execute_armor_source.index(
        '"state_type": "GodState", "value": True'
    )
    assert execute_armor_source.count('"state_type": "GodState", "value": False') == 1
    require(client_source, "AccumulatedStiffStack = PreviousStiffStack + stiff_value")

    tutorial_ui = json.loads(source(RESOURCE / "ui/TutorialScreen.json"))
    guide_children = {
        name.split("@", 1)[0]: value
        for entry in tutorial_ui["guide_overlay"]["controls"]
        for name, value in entry.items()
    }
    assert "MechanicStatus" in guide_children
    assert "mechanic_metric" in tutorial_ui
    assert_alpha_chain(guide_children["MechanicStatus"], "guide_overlay/MechanicStatus")
    assert_alpha_chain(tutorial_ui["mechanic_metric"], "mechanic_metric")
    ui_config_source = source(UI_DIR / "UIConfig.py")
    assert ui_config_source.count('TutorialGuideMechanic = TutorialGuide+"/MechanicStatus"') == 3

    catalog_source = source(UI_DIR / "TutorialCatalog.py")
    mechanics_source = catalog_source[catalog_source.index('"id": "mechanics"'):]
    assert "内容制作中" not in mechanics_source
    assert "_planned" not in mechanics_source
    for player_rule in (u"二级蓄力互撞不会拼刀", u"三级技能互撞会共同保持", u"终结技是四级并带强保护", u"完美格挡与反击全程无敌", u"用三次命中压住木偶", u"上挑后再追击木偶两次", u"击飞刷新", u"眩晕技能会刷新", u"处决会刷新"):
        assert player_rule in mechanics_source
    assert u"完美格挡反击是三级强保护" not in mechanics_source
    guide_source = source(ROOT / "剑魂教程引导.md")
    require(guide_source, u"提前释放反击会立即中止完美格挡原本的 3 秒无敌计时")
    require(guide_source, u"直到该动作完全结束")
    print("tutorial mechanics chapter regression: PASS")


if __name__ == "__main__":
    main()
