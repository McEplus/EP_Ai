#!/usr/bin/env python3
# coding=utf-8
"""Regression checks for animation-only contact candidate extraction."""

# Codex 2026-08-08: 回归旋转连击识别、时钟换算和候选非极大值抑制。

from __future__ import annotations

import importlib.util
import pathlib


PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[4]
SCRIPT_PATH = pathlib.Path(__file__).with_name("suggest_contact_frames.py")


def load_module():
    spec = importlib.util.spec_from_file_location("suggest_contact_frames", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    module = load_module()
    iron = module.analyze(
        PROJECT_ROOT / "src/SwordSoul_NewERA_R/animations/mob/iron_golem/fight_iron_golem.animation.json",
        animation_names=["attack_sneaking_2", "attack_sprint"],
        top=5,
    )
    by_name = dict((item["animation"].rsplit(".", 1)[-1], item) for item in iron["animations"])
    spin = by_name["attack_sneaking_2"]
    assert spin["continuous_spin"] is True
    assert abs(spin["root_rotation_span"][1]) >= 300.0
    assert spin["candidates"]
    assert any(item["motion_type"] == "continuous_spin" for item in spin["candidates"])

    sprint = by_name["attack_sprint"]
    assert sprint["anim_rate"] == 0.8782843137
    assert sprint["candidates"]
    for left, right in zip(sprint["candidates"], sprint["candidates"][1:]):
        assert right["source_time"] - left["source_time"] >= 0.15 - 1e-9
    for item in sprint["candidates"]:
        assert abs(item["state_time"] - item["source_time"] / sprint["anim_rate"]) < 1e-9

    warden = module.analyze(
        PROJECT_ROOT / "src/SwordSoul_NewERA_R/animations/mob/wraden/warden.animation.json",
        animation_names=["attack_third"],
        top=4,
    )
    third = warden["animations"][0]
    assert third["candidates"]
    assert all(item["dominant_bones"] for item in third["candidates"])
    text = module.render_markdown(warden)
    assert "Animation contact candidates" in text
    assert "source_time" in text
    print(
        "contact candidate checks passed: spin_span=%.1f sprint_candidates=%d warden_candidates=%d"
        % (spin["root_rotation_span"][1], len(sprint["candidates"]), len(third["candidates"]))
    )


if __name__ == "__main__":
    main()
