#!/usr/bin/env python3
# coding=utf-8
"""Suggest contact-frame candidates from Bedrock actor animation channels."""

# Codex 2026-08-08: 用局部骨骼速度峰生成命中候选，保留静态分析置信边界。

from __future__ import annotations

import argparse
import json
import math
import pathlib
import re
import sys


DEFAULT_BONE_PATTERN = r"(?:^root$|body|waist|arm|hand)"


def _configure_stdout():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")


def _read_json(path):
    with path.open("r", encoding="utf-8") as stream:
        return json.load(stream)


def _vector(value, prefer="post"):
    if isinstance(value, dict):
        value = value.get(prefer, value.get("post", value.get("pre")))
    if isinstance(value, (int, float)):
        return (float(value),) * 3
    if isinstance(value, list) and len(value) == 3:
        if all(isinstance(item, (int, float)) for item in value):
            return tuple(float(item) for item in value)
    return None


def _channel_keyframes(channel):
    if isinstance(channel, (int, float, list)):
        value = _vector(channel)
        return [(0.0, value, value, "constant")] if value is not None else []
    if not isinstance(channel, dict):
        return []
    result = []
    for raw_time, raw_value in channel.items():
        pre = _vector(raw_value, "pre")
        post = _vector(raw_value, "post")
        if pre is None or post is None:
            continue
        mode = raw_value.get("lerp_mode", "linear") if isinstance(raw_value, dict) else "linear"
        result.append((float(raw_time), pre, post, mode))
    return sorted(result)


def _sample(channel, source_time):
    keyframes = _channel_keyframes(channel)
    if not keyframes:
        return (0.0, 0.0, 0.0)
    if source_time <= keyframes[0][0]:
        return keyframes[0][1]
    if source_time >= keyframes[-1][0]:
        return keyframes[-1][2]
    for left, right in zip(keyframes, keyframes[1:]):
        if left[0] <= source_time <= right[0]:
            duration = max(right[0] - left[0], 0.000001)
            progress = (source_time - left[0]) / duration
            return tuple(
                left[2][axis] + (right[1][axis] - left[2][axis]) * progress
                for axis in range(3)
            )
    return keyframes[-1][2]


def _animation_rate(expression):
    if not expression:
        return 1.0
    match = re.fullmatch(
        r"(?:query|q)\.anim_time\s*\+\s*(?:query|q)\.delta_time\s*\*\s*([0-9]+(?:\.[0-9]+)?)",
        expression.strip(),
    )
    return float(match.group(1)) if match else None


def _angular_speed(channel, source_time, dt, animation_length):
    left_time = max(0.0, source_time - dt)
    right_time = min(animation_length, source_time + dt)
    duration = max(right_time - left_time, 0.000001)
    left = _sample(channel, left_time)
    right = _sample(channel, right_time)
    return math.sqrt(sum(((right[axis] - left[axis]) / duration) ** 2 for axis in range(3)))


def _root_rotation_span(animation):
    rotation = animation.get("bones", {}).get("root", {}).get("rotation")
    keyframes = _channel_keyframes(rotation)
    if not keyframes:
        return (0.0, 0.0, 0.0)
    values = []
    for _, pre, post, _ in keyframes:
        values.extend((pre, post))
    return tuple(max(value[axis] for value in values) - min(value[axis] for value in values) for axis in range(3))


def _root_net(animation):
    position = animation.get("bones", {}).get("root_move", {}).get("position")
    keyframes = _channel_keyframes(position)
    if not keyframes:
        return (0.0, 0.0, 0.0)
    first = keyframes[0][1]
    last = keyframes[-1][2]
    return tuple(last[axis] - first[axis] for axis in range(3))


def _classify(animation, dominant_bones, root_span, root_net):
    root_y_span = abs(root_span[1])
    if root_y_span >= 300.0:
        return "continuous_spin"
    names = set(dominant_bones)
    has_left = any("left_arm" in name for name in names)
    has_right = any("right_arm" in name for name in names)
    if has_left and has_right:
        return "bilateral_impact"
    root_distance = math.sqrt(sum(value * value for value in root_net))
    if root_distance >= 40.0:
        return "lunge_or_charge"
    return "single_swing"


def suggest_animation(animation_name, animation, sample_fps=48.0, top=5, min_gap=0.15, bone_pattern=DEFAULT_BONE_PATTERN):
    animation_length = float(animation.get("animation_length", 0.0) or 0.0)
    expression = animation.get("anim_time_update", "")
    rate = _animation_rate(expression)
    if rate is None:
        rate = 1.0
        rate_warning = "unparsed anim_time_update; state_time temporarily uses rate=1"
    else:
        rate_warning = None
    matcher = re.compile(bone_pattern, re.IGNORECASE)
    channels = {}
    has_catmullrom = False
    for bone_name, bone_data in animation.get("bones", {}).items():
        rotation = bone_data.get("rotation")
        if not matcher.search(bone_name) or rotation is None:
            continue
        channels[bone_name] = rotation
        if any(item[3] == "catmullrom" for item in _channel_keyframes(rotation)):
            has_catmullrom = True
    dt = 1.0 / max(sample_fps, 1.0)
    samples = []
    step_count = max(int(math.ceil(animation_length * sample_fps)), 1)
    for index in range(1, step_count):
        source_time = min(index / sample_fps, animation_length)
        speeds = sorted(
            ((_angular_speed(channel, source_time, dt, animation_length), bone_name) for bone_name, channel in channels.items()),
            reverse=True,
        )
        top_speeds = speeds[:3]
        combined = sum(value for value, _ in top_speeds)
        samples.append({
            "source_time": source_time,
            "combined_speed": combined,
            "dominant": top_speeds,
        })
    for index, item in enumerate(samples):
        next_speed = samples[index + 1]["combined_speed"] if index + 1 < len(samples) else 0.0
        deceleration = max(0.0, item["combined_speed"] - next_speed)
        item["score"] = item["combined_speed"] + deceleration * 0.5
    chosen = []
    for item in sorted(samples, key=lambda value: value["score"], reverse=True):
        if any(abs(item["source_time"] - old["source_time"]) < min_gap for old in chosen):
            continue
        chosen.append(item)
        if len(chosen) >= top:
            break
    chosen.sort(key=lambda value: value["source_time"])
    root_span = _root_rotation_span(animation)
    root_net = _root_net(animation)
    candidates = []
    for item in chosen:
        dominant_bones = [name for _, name in item["dominant"]]
        candidates.append({
            "source_time": item["source_time"],
            "state_time": item["source_time"] / rate,
            "score": item["score"],
            "dominant_bones": dominant_bones,
            "dominant_speeds": [value for value, _ in item["dominant"]],
            "motion_type": _classify(animation, dominant_bones, root_span, root_net),
        })
    warnings = []
    if rate_warning:
        warnings.append(rate_warning)
    if has_catmullrom:
        warnings.append("catmullrom channels were sampled with a linear approximation")
    if not channels:
        warnings.append("no matching rotation channels")
    return {
        "animation": animation_name,
        "animation_length": animation_length,
        "anim_time_update": expression,
        "anim_rate": rate,
        "root_rotation_span": root_span,
        "root_net": root_net,
        "continuous_spin": abs(root_span[1]) >= 300.0,
        "candidates": candidates,
        "warnings": warnings,
    }


def analyze(animation_json, animation_names=None, sample_fps=48.0, top=5, min_gap=0.15, bone_pattern=DEFAULT_BONE_PATTERN):
    animations = _read_json(animation_json).get("animations", {})
    selected = []
    if animation_names:
        for requested in animation_names:
            matches = [(name, value) for name, value in animations.items() if name == requested or name.endswith("." + requested)]
            if len(matches) != 1:
                raise ValueError("animation %s expected once, found %d" % (requested, len(matches)))
            selected.append(matches[0])
    else:
        selected = [(name, value) for name, value in animations.items() if ".attack_" in name]
    return {
        "animation_json": str(animation_json),
        "sample_fps": sample_fps,
        "top": top,
        "min_gap": min_gap,
        "animations": [
            suggest_animation(name, value, sample_fps=sample_fps, top=top, min_gap=min_gap, bone_pattern=bone_pattern)
            for name, value in selected
        ],
    }


def render_markdown(report):
    lines = [
        "# Animation contact candidates",
        "",
        "- Source: `%s`" % report["animation_json"],
        "- Sampling: `%s fps`, min gap `%ss`" % (report["sample_fps"], report["min_gap"]),
    ]
    for animation in report["animations"]:
        lines.extend([
            "",
            "## %s" % animation["animation"],
            "",
            "Root rotation span `%s`; root net `%s`; continuous spin `%s`."
            % (animation["root_rotation_span"], animation["root_net"], animation["continuous_spin"]),
            "",
            "| source_time | state_time | type | dominant bones | score |",
            "|---:|---:|---|---|---:|",
        ])
        for item in animation["candidates"]:
            lines.append(
                "| %.4f | %.4f | %s | %s | %.1f |"
                % (
                    item["source_time"],
                    item["state_time"],
                    item["motion_type"],
                    ", ".join(item["dominant_bones"]),
                    item["score"],
                )
            )
        for warning in animation["warnings"]:
            lines.append("- Warning: %s" % warning)
    return "\n".join(lines) + "\n"


def main(argv=None):
    _configure_stdout()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--animation-json", required=True, type=pathlib.Path)
    parser.add_argument("--animation", dest="animation_names", action="append")
    parser.add_argument("--sample-fps", type=float, default=48.0)
    parser.add_argument("--top", type=int, default=5)
    parser.add_argument("--min-gap", type=float, default=0.15)
    parser.add_argument("--bone-pattern", default=DEFAULT_BONE_PATTERN)
    parser.add_argument("--format", choices=("markdown", "json"), default="markdown")
    args = parser.parse_args(argv)
    report = analyze(
        args.animation_json,
        animation_names=args.animation_names,
        sample_fps=args.sample_fps,
        top=args.top,
        min_gap=args.min_gap,
        bone_pattern=args.bone_pattern,
    )
    if args.format == "json":
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(render_markdown(report), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
