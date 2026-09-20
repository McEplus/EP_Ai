#!/usr/bin/env python3
"""教程实机提示层在高 GUI 缩放下的静态防重叠检查。"""

from __future__ import print_function

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
RESOURCE = ROOT / "src/SwordSoul_NewERA_R/ui"


def load(name):
    return json.loads((RESOURCE / name).read_text(encoding="utf-8"))


def child_map(control):
    return {
        name.split("@", 1)[0]: value
        for entry in control.get("controls", [])
        for name, value in entry.items()
    }


def find_named(value, expected_name):
    if isinstance(value, dict):
        for name, child in value.items():
            if name.split("@", 1)[0] == expected_name:
                return child
            found = find_named(child, expected_name)
            if found is not None:
                return found
    elif isinstance(value, list):
        for child in value:
            found = find_named(child, expected_name)
            if found is not None:
                return found
    return None


def vertical_interval(control):
    return control["offset"][1], control["offset"][1] + control["size"][1]


def bottom_interval(control):
    return control["offset"][1] - control["size"][1], control["offset"][1]


def resolve_axis(value, total):
    if isinstance(value, (int, float)):
        return float(value)
    match = re.match(r"^(-?\d+(?:\.\d+)?)%\+(-?\d+(?:\.\d+)?)px$", value)
    assert match, value
    return float(match.group(1)) * total / 100.0 + float(match.group(2))


def top_interval(control, total=120.0):
    start = resolve_axis(control["offset"][1], total)
    return start, start + resolve_axis(control["size"][1], total)


def bottom_anchored_interval(control, total=768.0):
    end = total + resolve_axis(control["offset"][1], total)
    return end - resolve_axis(control["size"][1], total), end


def assert_before(first, second, label):
    assert first[1] <= second[0], "%s overlap: %r and %r" % (label, first, second)


def main():
    tutorial = load("TutorialScreen.json")
    guide = tutorial["guide_overlay"]
    assert guide["anchor_from"] == "top_left"
    assert guide["size"] == ["100%+0px", "100%+0px"]
    children = child_map(guide)

    # Codex 2026-07-22: 简要说明缩到左侧，阶段与机制进度改到右上方，二者水平分栏不遮挡。
    assert children["Background"]["anchor_from"] == "top_left"
    assert children["Background"]["offset"] == ["1.5%+0px", "24%+0px"]
    assert children["Background"]["size"] == ["30%+0px", 62]
    assert children["Accent"]["offset"] == children["Background"]["offset"]
    assert children["Accent"]["size"][1] == 62
    step = top_interval(children["Step"])
    title = top_interval(children["Title"])
    instruction = top_interval(children["Instruction"])
    hint = top_interval(children["Hint"])
    assert_before(step, title, "step/title")
    assert_before(title, instruction, "title/instruction")
    assert_before(instruction, hint, "instruction/hint")
    summary = top_interval(children["Background"])
    assert summary[0] <= step[0] and hint[1] <= summary[1]
    mode = top_interval(children["ModeBanner"], 768.0)
    summary_at_game_height = top_interval(children["Background"], 768.0)
    assert_before(mode, summary_at_game_height, "mode banner/summary")

    stage = top_interval(children["StageGuide"])
    mechanic = top_interval(children["MechanicStatus"])
    assert children["StageGuide"]["anchor_from"] == "top_left"
    assert children["MechanicStatus"]["anchor_from"] == "top_left"
    assert_before(stage, mechanic, "stage/mechanic")
    assert children["WindowCue"]["anchor_from"] == "bottom_middle"
    assert children["WindowCue"]["anchor_to"] == "bottom_middle"
    assert children["WindowCue"]["offset"] == [0, "-22%+0px"]
    window = bottom_anchored_interval(children["WindowCue"])
    continue_button = bottom_anchored_interval(children["Continue"])
    mechanic_at_game_height = top_interval(children["MechanicStatus"], 768.0)
    assert_before(mechanic_at_game_height, window, "upper progress/lower timing cue")
    assert window[1] <= 0.8 * 768.0
    assert_before(window, continue_button, "lower timing cue/continue button")
    assert children["Continue"]["offset"] == [0, "-15%+0px"]
    assert children["Continue"]["visible"] is False
    assert children["WindowCue"]["layer"] > children["MechanicStatus"]["layer"]
    assert mechanic[1] <= 120.0
    summary_right = 1.5 + 30.0
    progress_left = 34.0
    assert summary_right < progress_left
    assert resolve_axis(children["StageGuide"]["offset"][0], 100.0) + resolve_axis(
        children["StageGuide"]["size"][0], 100.0
    ) <= 90.0
    assert children["Cancel"]["offset"][0] == "80%+0px"
    assert children["Cancel"]["size"][0] == "10%+0px"

    stage_children = child_map(children["StageGuide"])
    stage_title = vertical_interval(stage_children["Title"])
    stage_card_height = tutorial["guide_stage"]["size"][1]
    stage_card_bottom = children["StageGuide"]["size"][1] + stage_children["Stage1"]["offset"][1]
    stage_card = stage_card_bottom - stage_card_height, stage_card_bottom
    assert_before(stage_title, stage_card, "stage title/card")

    metric = child_map(tutorial["mechanic_metric"])
    metric_title = vertical_interval(metric["Title"])
    metric_value = vertical_interval(metric["Value"])
    metric_progress_bottom = tutorial["mechanic_metric"]["size"][1] + metric["Progress"]["offset"][1]
    metric_progress = metric_progress_bottom - metric["Progress"]["size"][1], metric_progress_bottom
    assert_before(metric_title, metric_value, "metric title/value")
    assert_before(metric_value, metric_progress, "metric value/progress")

    # 三个实际载体都保留全屏坐标系，保证左侧说明和右上进度使用一致位置。
    # Codex 2026-07-22: 实机 HUD 挂载点继承全屏；设置页与表情页保留各自原生容器的裁剪范围。
    control_instance = find_named(load("Control.json"), "TutorialGuide")
    assert control_instance == {}, control_instance
    for file_name, expected_size in (
        ("MainSetting.json", ["58%+0px", "94%+0px"]),
        ("EmojiUi.json", ["72%+0px", "94%+0px"]),
    ):
        instance = find_named(load(file_name), "TutorialGuide")
        assert instance is not None, file_name
        assert instance["size"] == expected_size, (file_name, instance["size"])

    print("tutorial high-GUI-scale layout regression: PASS")


if __name__ == "__main__":
    main()
