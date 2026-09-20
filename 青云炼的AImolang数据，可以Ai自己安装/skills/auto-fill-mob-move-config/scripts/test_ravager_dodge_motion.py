#!/usr/bin/env python3
# coding=utf-8
"""Lock Ravager four-way dodge motion to its authored root_move curves."""

from __future__ import annotations

import ast
import json
import pathlib


PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[4]
ENTITY_PATH = PROJECT_ROOT / "src/SwordSoul_NewERA_B/SwordSoulMobFightScripts/Entities/RavagerMob.py"
ANIMATION_PATH = PROJECT_ROOT / "src/SwordSoul_NewERA_R/animations/mob/ravager/fight_ravager.animation.json"
GEOMETRY_PATH = PROJECT_ROOT / "src/SwordSoul_NewERA_R/models/entity/mob/Ravager.geo.json"

DODGES = {
    "RavagerDodgeForward": ((0, 0, 1), "animation.arris_ravager.dodge_forward", (0, 0, -116)),
    "RavagerDodgeBack": ((0, 0, -1), "animation.arris_ravager.dodge_back", (0, 0, 116)),
    "RavagerDodgeLeft": ((1, 0, 0), "animation.arris_ravager.dodge_left", (116, 0, 0)),
    "RavagerDodgeRight": ((-1, 0, 0), "animation.arris_ravager.dodge_right", (-116, 0, 0)),
}
BUDGES = {
    "RavagerBudgeForward": "RavagerDodgeForward",
    "RavagerBudgeBack": "RavagerDodgeBack",
    "RavagerBudgeLeft": "RavagerDodgeLeft",
    "RavagerBudgeRight": "RavagerDodgeRight",
}
EXPECTED_TIMES = [round(0.0833 + index * 0.05, 4) for index in range(15)]
EXPECTED_POWERS = [
    0.509670, 0.739340, 0.834505, 0.795165, 0.621320,
    0.459812, 0.289205, 0.245619, 0.329056, 0.378505,
    0.442224, 0.475969, 0.459638, 0.393229, 0.276743,
]


def function(class_node, name):
    return next(node for node in class_node.body if isinstance(node, ast.FunctionDef) and node.name == name)


def literal(node):
    return ast.literal_eval(node)


def assigned_windows(init_node):
    result = {}
    for node in init_node.body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name) and target.value.id == "self":
            if target.attr in ("UnControlTime", "StateKeepTime", "StateAnimTime"):
                result[target.attr] = literal(node.value)
    return result


def endpoint(position):
    final = position[sorted(position, key=float)[-1]]
    if isinstance(final, dict):
        final = final.get("post", final.get("pre"))
    return tuple(final)


def main():
    source = ENTITY_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(ENTITY_PATH))
    classes = dict((node.name, node) for node in tree.body if isinstance(node, ast.ClassDef))

    # Codex 2026-08-09: Never let Ravager budges silently fall back to generic EmptyBudge motion.
    names = set(node.id for node in ast.walk(tree) if isinstance(node, ast.Name))
    assert not names.intersection({
        "EmptyBudgeForward", "EmptyBudgeBack", "EmptyBudgeLeft", "EmptyBudgeRight",
    })

    for class_name, (direction, _, _) in DODGES.items():
        class_node = classes[class_name]
        assert assigned_windows(function(class_node, "__init__")) == {
            "UnControlTime": 0.85,
            "StateKeepTime": 0.9,
            "StateAnimTime": 1.25,
        }
        on_start = function(class_node, "onStart")
        base_starts = [
            node for node in ast.walk(on_start)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "onStart"
        ]
        assert not base_starts, class_name

        schedules = [
            node for node in ast.walk(on_start)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "ScheduleRootMotionTicks"
        ]
        assert len(schedules) == 1, class_name
        assert isinstance(schedules[0].args[0], ast.Tuple), class_name
        records = literal(schedules[0].args[0])
        assert [record[0] for record in records] == EXPECTED_TIMES, class_name
        assert [record[1] for record in records] == [direction] * 15, class_name
        assert [record[2] for record in records] == EXPECTED_POWERS, class_name
        assert abs(sum(record[2] for record in records) - 7.25) < 0.000001, class_name

        stop_times = [
            literal(node.args[0]) for node in ast.walk(on_start)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "StateAnim_CreateTimer"
            and len(node.args) >= 5
            and literal(node.args[3]) == (0, 0, 0)
        ]
        assert stop_times == [0.8333, 1.25], (class_name, stop_times)

    for class_name, expected_base in BUDGES.items():
        class_node = classes[class_name]
        assert [base.id for base in class_node.bases if isinstance(base, ast.Name)] == [expected_base]
        assert not any(isinstance(node, ast.FunctionDef) and node.name == "onStart" for node in class_node.body)

    animations = json.loads(ANIMATION_PATH.read_text(encoding="utf-8"))["animations"]
    for _, (_, animation_name, expected_endpoint) in DODGES.items():
        animation = animations[animation_name]
        assert animation["animation_length"] == 1.25
        assert "anim_time_update" not in animation
        root_position = animation["bones"]["root_move"]["position"]
        assert endpoint(root_position) == expected_endpoint

    geometry = json.loads(GEOMETRY_PATH.read_text(encoding="utf-8"))
    bone_names = {
        bone["name"]
        for entry in geometry["minecraft:geometry"]
        for bone in entry.get("bones", [])
    }
    assert "root_move" not in bone_names
    print("ravager dodge motion checks passed: directions=4 distance=7.25 ticks=15 budges=4")


if __name__ == "__main__":
    main()
