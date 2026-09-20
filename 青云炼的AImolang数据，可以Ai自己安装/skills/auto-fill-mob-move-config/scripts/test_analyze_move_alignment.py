#!/usr/bin/env python3
# coding=utf-8
"""Regression checks for the calibrated mob move evidence extractor."""

# Codex 2026-08-08: 用两只已调准生物回归自动填参分析器的关键推导能力。

from __future__ import annotations

import importlib.util
import pathlib


PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[4]
SCRIPT_PATH = pathlib.Path(__file__).with_name("analyze_move_alignment.py")


def load_analyzer():
    spec = importlib.util.spec_from_file_location("mob_move_alignment", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def find_one(name):
    matches = [path for path in PROJECT_ROOT.rglob(name) if ".build" not in path.parts]
    assert len(matches) == 1, (name, matches)
    return matches[0]


def by_suffix(report):
    return dict((item["suffix"], item) for item in report["moves"])


def assert_motion_scale(move):
    value = move["implied_motion_scale"]
    assert value is not None, move["suffix"]
    # 旧配置只保留两位功率时允许少量舍入误差。
    assert 0.0050 <= value <= 0.0056, (move["suffix"], value)


def main():
    analyzer = load_analyzer()
    warden = analyzer.analyze(
        PROJECT_ROOT / "src/SwordSoul_NewERA_B/SwordSoulMobFightScripts/Entities/WardenMob.py",
        PROJECT_ROOT / "src/SwordSoul_NewERA_R/animations/mob/wraden/warden.animation.json",
        bbmodel=find_one("fight_warden.bbmodel"),
    )
    iron = analyzer.analyze(
        PROJECT_ROOT / "src/SwordSoul_NewERA_B/SwordSoulMobFightScripts/Entities/IronGolemMob.py",
        PROJECT_ROOT / "src/SwordSoul_NewERA_R/animations/mob/iron_golem/fight_iron_golem.animation.json",
        bbmodel=find_one("fight_iron_golem.bbmodel"),
    )
    ravager = analyzer.analyze(
        PROJECT_ROOT / "src/SwordSoul_NewERA_B/SwordSoulMobFightScripts/Entities/RavagerMob.py",
        PROJECT_ROOT / "src/SwordSoul_NewERA_R/animations/mob/ravager/fight_ravager.animation.json",
        bbmodel=find_one("fight_ravager.bbmodel"),
    )
    ravager_mobility = analyzer.analyze(
        PROJECT_ROOT / "src/SwordSoul_NewERA_B/SwordSoulMobFightScripts/Entities/RavagerMob.py",
        PROJECT_ROOT / "src/SwordSoul_NewERA_R/animations/mob/ravager/fight_ravager.animation.json",
        bbmodel=find_one("fight_ravager.bbmodel"),
        class_names=(
            "RavagerDodgeForward", "RavagerDodgeBack", "RavagerDodgeLeft", "RavagerDodgeRight",
        ),
    )
    warden_moves = by_suffix(warden)
    iron_moves = by_suffix(iron)
    ravager_moves = by_suffix(ravager)
    ravager_mobility_moves = by_suffix(ravager_mobility)
    expected = {
        "attack_first",
        "attack_second",
        "attack_third",
        "attack_sprint",
        "attack_execute",
        "attack_sneaking_1",
        "attack_sneaking_2",
    }
    assert set(warden_moves) == expected
    assert set(iron_moves) == expected
    assert set(ravager_moves) == {
        "attack_first", "attack_second", "attack_third", "attack_sprint",
        "attack_sneaking_1", "attack_sneaking_2",
    }
    assert not ravager["missing_animations"]
    assert set(ravager_mobility_moves) == {
        "dodge_forward", "dodge_back", "dodge_left", "dodge_right",
    }
    assert not ravager_mobility["missing_animations"]
    for move in list(warden_moves.values()) + list(iron_moves.values()):
        assert_motion_scale(move)

    warden_execute = warden_moves["attack_execute"]
    assert warden_execute["attacks"][-1]["shape"] == "ground_corridor"
    execute_dirt = [item for item in warden_execute["effects"] if item["kind"] == "DirtSmoke"]
    assert len(execute_dirt) == 10
    execute_offsets = [item["args"][1][2] for item in execute_dirt]
    assert execute_offsets == list(range(2, 21, 2))

    warden_sneak = warden_moves["attack_sneaking_1"]
    assert warden_sneak["attacks"][0]["shape"] == "ground_corridor"
    sneak_dirt = [item for item in warden_sneak["effects"] if item["kind"] == "DirtSmoke"]
    assert [item["args"][1][2] for item in sneak_dirt] == list(range(2, 21, 2))

    iron_spin = iron_moves["attack_sneaking_2"]
    rapid_times = [item["time"] for item in iron_spin["attacks"] if item["shape"] == "radial"]
    assert rapid_times == [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8]
    assert "EmptyAttackSneaking2" in iron_spin["base_on_start"]
    assert any(item["code"] == "inherited-on-start-not-expanded" for item in iron_spin["warnings"])

    # Codex 2026-08-09: 回归劫掠兽专属类名、双段攻击和新动画 root_move 的完整读取。
    ravager_hit_times = {
        suffix: [item["time"] for item in move["attacks"]]
        for suffix, move in ravager_moves.items()
    }
    assert ravager_hit_times == {
        "attack_first": [0.3],
        "attack_second": [0.52],
        "attack_third": [0.1],
        "attack_sprint": [0.43],
        "attack_sneaking_1": [0.55],
        "attack_sneaking_2": [0.53, 1.76],
    }
    for suffix in ("attack_second", "attack_third", "attack_sprint"):
        assert ravager_moves[suffix]["root_integral_error"] < 0.0002, suffix
    assert max(abs(value) for value in ravager_moves["attack_sneaking_2"]["motion_net"]) < 0.0002
    assert [item["kind"] for item in ravager_moves["attack_sprint"]["effects"]] == [
        "SprintDirtSmoke", "PlayPunchAirFlow", "PlayPunchSonicBoom",
    ]
    assert [item["kind"] for item in ravager_moves["attack_sneaking_2"]["effects"]].count(
        "PlayPunchSonicBoom"
    ) == 1
    mobility_directions = {
        "dodge_forward": (0.0, 0.0, 1.0),
        "dodge_back": (0.0, 0.0, -1.0),
        "dodge_left": (1.0, 0.0, 0.0),
        "dodge_right": (-1.0, 0.0, 0.0),
    }
    ravager_tick_powers = [
        0.509670, 0.739340, 0.834505, 0.795165, 0.621320, 0.459812, 0.289205,
        0.245619, 0.329056, 0.378505, 0.442224, 0.475969, 0.459638, 0.393229,
        0.276743,
    ]
    for suffix, move in ravager_mobility_moves.items():
        # Codex 2026-08-09: 锁定 116 模型单位按 20Hz 重放为 7.25 格，防止把瞬时速度误作持续秒位移。
        assert move["root_integral_error"] < 0.0002, suffix
        direction = mobility_directions[suffix]
        tick_motions = [item for item in move["motions"] if item.get("integration") == "tick_delta"]
        assert [item["time"] for item in tick_motions] == [round(0.0833 + index * 0.05, 4) for index in range(15)], suffix
        assert [item["direction"] for item in tick_motions] == [direction] * 15, suffix
        assert [item["power"] for item in tick_motions] == ravager_tick_powers, suffix
        assert move["motion_integration"] == "tick_delta", suffix
        assert move["effective_motion_scale"] == 1.0 / 16.0, suffix
        assert abs(sum(abs(value) for value in move["motion_net"]) - 7.25) < 0.000001, suffix
        assert move["windows"] == {
            "UnControlTime": 0.85,
            "StateKeepTime": 0.9,
            "StateAnimTime": 1.25,
        }, suffix
        assert [item["kind"] for item in move["effects"]] == ["DodgeDirtSmoke"], suffix
        assert move["motions"][-1] == {
            "time": 1.25, "direction": (0.0, 0.0, 0.0), "power": 0.0, "local": False,
        }, suffix

    for report in (warden, iron, ravager, ravager_mobility):
        text = analyzer.render_markdown(report)
        assert "Mob move alignment audit" in text
        assert "Implied scale" in text
    print(
        "mob move alignment checks passed: warden=%d iron_golem=%d ravager=%d mobility=%d "
        "legacy_root_scale=0.00527 ravager_root_scale=0.0625 corridors=2 spin_hits=%d"
        % (
            len(warden_moves), len(iron_moves), len(ravager_moves),
            len(ravager_mobility_moves), len(rapid_times),
        )
    )


if __name__ == "__main__":
    main()
