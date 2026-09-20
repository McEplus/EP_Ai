#!/usr/bin/env python3
# coding=utf-8
"""Lock Enderman root curves to Iron-Golem-style direct motion timers."""

from __future__ import annotations

import ast
import json
import math
import pathlib
import re


PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[4]
ENTITY_PATH = PROJECT_ROOT / "src/SwordSoul_NewERA_B/SwordSoulMobFightScripts/Entities/EndermanMob.py"
ANIMATION_PATH = PROJECT_ROOT / "src/SwordSoul_NewERA_R/animations/mob/enderman/fight_enderman.animation.json"
BBMODEL_PATH = next(PROJECT_ROOT.glob("*/*/fight_enderman.bbmodel"))

ROOT_MOVES = {
    "EndermanAttackFirst": "attack_first",
    "EndermanAttackSecond": "attack_second",
    "EndermanAttackThird": "attack_third",
    "EndermanAttackSprint": "attack_sprint",
    "EndermanAttackExecute": "attack_execute",
    "EndermanAttackSneaking1": "attack_sneaking_1",
    "EndermanAttackSneaking2": "attack_sneaking_2",
    "EndermanDodgeForward": "dodge_forward",
    "EndermanDodgeBack": "dodge_back",
    "EndermanDodgeLeft": "dodge_left",
    "EndermanDodgeRight": "dodge_right",
}
BUDGES = {
    "EndermanBudgeForward": "EndermanDodgeForward",
    "EndermanBudgeBack": "EndermanDodgeBack",
    "EndermanBudgeLeft": "EndermanDodgeLeft",
    "EndermanBudgeRight": "EndermanDodgeRight",
}
RATE_PATTERN = re.compile(r"query\.anim_time \+ query\.delta_time \* ([0-9.]+)")


def vector(raw_value):
    if isinstance(raw_value, dict):
        raw_value = raw_value.get("post", raw_value.get("pre"))
    return tuple(float(value) for value in raw_value)


def keyframes(channel):
    if isinstance(channel, list):
        return [(0.0, vector(channel), "linear")]
    return sorted(
        (
            float(time_point),
            vector(value),
            value.get("lerp_mode", "linear") if isinstance(value, dict) else "linear",
        )
        for time_point, value in channel.items()
    )


def sample(channel, time_point):
    frames = keyframes(channel)
    if time_point <= frames[0][0]:
        return frames[0][1]
    if time_point >= frames[-1][0]:
        return frames[-1][1]
    for index in range(1, len(frames)):
        end_time, end_value, _ = frames[index]
        if time_point > end_time:
            continue
        start_time, start_value, mode = frames[index - 1]
        progress = (time_point - start_time) / (end_time - start_time)
        if mode != "catmullrom":
            return tuple(
                start_value[axis] + (end_value[axis] - start_value[axis]) * progress
                for axis in range(3)
            )
        before = frames[max(0, index - 2)][1]
        after = frames[min(len(frames) - 1, index + 1)][1]
        progress2 = progress * progress
        progress3 = progress2 * progress
        return tuple(
            0.5 * (
                2.0 * start_value[axis]
                + (-before[axis] + end_value[axis]) * progress
                + (
                    2.0 * before[axis]
                    - 5.0 * start_value[axis]
                    + 4.0 * end_value[axis]
                    - after[axis]
                ) * progress2
                + (
                    -before[axis]
                    + 3.0 * start_value[axis]
                    - 3.0 * end_value[axis]
                    + after[axis]
                ) * progress3
            )
            for axis in range(3)
        )
    raise AssertionError("unreachable root-motion sample")


def expected_schedule(animation):
    duration = float(animation["animation_length"])
    rate_match = RATE_PATTERN.fullmatch(animation["anim_time_update"])
    assert rate_match, animation.get("anim_time_update")
    rate = float(rate_match.group(1))
    channel = animation["bones"]["root_move"]["position"]
    previous = sample(channel, 0.0)
    result = []
    for tick_index in range(int(math.ceil(duration * 20.0 - 0.000000001))):
        current = sample(channel, min(duration, (tick_index + 1) / 20.0))
        delta = (
            (current[0] - previous[0]) / 16.0,
            (current[1] - previous[1]) / 16.0,
            (previous[2] - current[2]) / 16.0,
        )
        magnitude = math.sqrt(sum(value * value for value in delta))
        if magnitude > 0.00000001:
            direction = tuple(value / magnitude for value in delta)
            result.append((tick_index / 20.0 / rate, direction, magnitude))
        previous = current
    return result


def function(class_node, name):
    return next(
        node
        for node in class_node.body
        if isinstance(node, ast.FunctionDef) and node.name == name
    )


def state_anim_time(class_node):
    init_node = function(class_node, "__init__")
    return next(
        ast.literal_eval(node.value)
        for node in init_node.body
        if isinstance(node, ast.Assign)
        and isinstance(node.targets[0], ast.Attribute)
        and node.targets[0].attr == "StateAnimTime"
    )


def motion_power(node):
    assert isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mult), ast.dump(node)
    constant = node.left if isinstance(node.left, ast.Constant) else node.right
    scale = node.right if constant is node.left else node.left
    assert isinstance(constant, ast.Constant) and isinstance(constant.value, (int, float))
    assert isinstance(scale, ast.Attribute) and scale.attr == "State_MotionPower"
    assert isinstance(scale.value, ast.Name) and scale.value.id == "self"
    return float(constant.value)


def assert_set_move_assignment(on_start, class_name):
    assignments = [
        node
        for node in on_start.body
        if isinstance(node, ast.Assign)
        and len(node.targets) == 1
        and isinstance(node.targets[0], ast.Name)
        and node.targets[0].id == "SetMoveMotion"
    ]
    assert len(assignments) == 1, class_name
    value = assignments[0].value
    assert isinstance(value, ast.Attribute) and value.attr == "SetMoveMotion"
    assert isinstance(value.value, ast.Attribute) and value.value.attr == "PlayerRootController"
    assert isinstance(value.value.value, ast.Name) and value.value.value.id == "self"


def assert_root_schedule(class_node, animation):
    on_start = function(class_node, "onStart")
    assert_set_move_assignment(on_start, class_node.name)
    motion_if = next(
        node
        for node in on_start.body
        if isinstance(node, ast.If)
        and isinstance(node.test, ast.Name)
        and node.test.id == "StateMotion"
    )
    assert not any(
        isinstance(node, (ast.For, ast.While, ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp))
        for node in ast.walk(motion_if)
    ), class_node.name

    direct_calls = [
        node.value
        for node in motion_if.body
        if isinstance(node, ast.Expr)
        and isinstance(node.value, ast.Call)
        and isinstance(node.value.func, ast.Name)
        and node.value.func.id == "SetMoveMotion"
    ]
    assert len(direct_calls) == 1, class_node.name
    assert isinstance(motion_if.body[0], ast.Expr) and motion_if.body[0].value is direct_calls[0]

    timer_calls = [
        node.value
        for node in motion_if.body
        if isinstance(node, ast.Expr)
        and isinstance(node.value, ast.Call)
        and isinstance(node.value.func, ast.Attribute)
        and node.value.func.attr == "StateAnim_CreateTimer"
        and len(node.value.args) >= 5
        and isinstance(node.value.args[1], ast.Name)
        and node.value.args[1].id == "SetMoveMotion"
    ]
    assert timer_calls, class_node.name

    records = [(
        0.0,
        ast.literal_eval(direct_calls[0].args[0]),
        motion_power(direct_calls[0].args[1]),
    )]
    records.extend(
        (
            float(ast.literal_eval(call.args[0])),
            ast.literal_eval(call.args[3]),
            motion_power(call.args[4]),
        )
        for call in timer_calls
    )
    actual = [record for record in records if record[2] > 0.00000001]
    expected = expected_schedule(animation)
    assert len(actual) == len(expected), (class_node.name, len(actual), len(expected))
    for actual_record, expected_record in zip(actual, expected):
        assert abs(actual_record[0] - expected_record[0]) < 0.00015
        assert max(
            abs(actual_record[1][axis] - expected_record[1][axis])
            for axis in range(3)
        ) < 0.000002
        assert abs(actual_record[2] - expected_record[2]) < 0.000002

    stop_times = [
        float(ast.literal_eval(call.args[0]))
        for call in timer_calls
        if ast.literal_eval(call.args[3]) == (0, 0, 0)
        and abs(motion_power(call.args[4])) < 0.00000001
    ]
    assert state_anim_time(class_node) in stop_times, (class_node.name, stop_times)


def assert_bbmodel_root(animation_name, animation, bb_animation):
    root = animation.get("bones", {}).get("root_move")
    if not root:
        return
    bb_root = next(
        animator
        for animator in bb_animation["animators"].values()
        if animator.get("name") == "root_move"
    )
    for channel_name in ("position", "rotation"):
        channel = root.get(channel_name)
        if channel is None:
            continue
        actor_frames = keyframes(channel)
        bb_frames = []
        for frame in bb_root["keyframes"]:
            if frame["channel"] != channel_name:
                continue
            data = frame["data_points"][-1]
            bb_frames.append((
                float(frame["time"]),
                (float(data["x"]), float(data["y"]), float(data["z"])),
                frame.get("interpolation", "linear"),
            ))
        bb_frames.sort()
        assert len(actor_frames) == len(bb_frames), (animation_name, channel_name)
        for actor_frame, bb_frame in zip(actor_frames, bb_frames):
            assert abs(actor_frame[0] - bb_frame[0]) < 0.00005
            assert max(
                abs(actor_frame[1][axis] - bb_frame[1][axis])
                for axis in range(3)
            ) < 0.00005
            assert actor_frame[2] == bb_frame[2]


def main():
    source = ENTITY_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(ENTITY_PATH))
    assert not any(isinstance(node, ast.FunctionDef) for node in tree.body)
    assert "ScheduleRootMotionTicks" not in source
    assert "self.GetComponent" not in source
    assert "BASE_ATTACK" not in source
    classes = {
        node.name: node
        for node in tree.body
        if isinstance(node, ast.ClassDef)
    }
    animations = json.loads(ANIMATION_PATH.read_text(encoding="utf-8"))["animations"]
    for class_name, suffix in ROOT_MOVES.items():
        assert_root_schedule(
            classes[class_name],
            animations["animation.fight_enderman." + suffix],
        )

    for class_name, expected_base in BUDGES.items():
        bases = [
            base.id
            for base in classes[class_name].bases
            if isinstance(base, ast.Name)
        ]
        assert bases == [expected_base], (class_name, bases)

    bbmodel = json.loads(BBMODEL_PATH.read_text(encoding="utf-8"))
    bb_animations = {
        animation["name"]: animation
        for animation in bbmodel["animations"]
    }
    assert set(animations) == set(bb_animations)
    for animation_name, animation in animations.items():
        assert animation_name.startswith("animation.fight_enderman.")
        assert_bbmodel_root(animation_name, animation, bb_animations[animation_name])

    sprint = animations["animation.fight_enderman.attack_sprint"]
    sprint_rate = float(RATE_PATTERN.fullmatch(sprint["anim_time_update"]).group(1))
    sprint_root = sprint["bones"]["root_move"]["position"]
    sprint_end = vector(sprint_root[sorted(sprint_root, key=float)[-1]])
    assert abs(float(sprint["animation_length"]) / sprint_rate - 2.04) < 0.0001
    assert sprint_end == (0.0, 0.0, -178.0)
    print(
        "enderman root-motion checks passed: classes=11 sprint_source=1.3333 "
        "sprint_visual=2.04 sprint_net=11.125 format=iron_golem_direct_timers "
        "BBModel_actor_root=exact"
    )


if __name__ == "__main__":
    main()
