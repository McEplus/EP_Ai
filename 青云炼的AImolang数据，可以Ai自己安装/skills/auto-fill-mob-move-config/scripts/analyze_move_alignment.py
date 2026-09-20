#!/usr/bin/env python3
# coding=utf-8
"""Offline audit for SWS mob move timing, motion, hitboxes, and VFX."""

# Codex 2026-08-08: 从实体状态与动画资源生成统一招式时间轴和对齐警告。

from __future__ import annotations

import argparse
import ast
import json
import math
import pathlib
import re
import sys


DYNAMIC = "<dynamic>"
WINDOW_FIELDS = ("AttackTime", "UnControlTime", "StateKeepTime", "StateAnimTime")
KNOWN_EFFECTS = {
    "PunchAirFlow",
    "PunchSonicBoom",
    "DirtSmoke",
    "DodgeDirtSmoke",
    "SprintDirtSmoke",
}


def _configure_stdout():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")


def _dotted_name(node):
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _dotted_name(node.value)
        return (base + "." if base else "") + node.attr
    return ""


def _is_state_motion_power(node):
    return (
        isinstance(node, ast.Attribute)
        and node.attr == "State_MotionPower"
        and isinstance(node.value, ast.Name)
        and node.value.id == "self"
    )


def _eval_node(node):
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Name):
        if node.id in ("playerId", "entityId"):
            return DYNAMIC
        return DYNAMIC + ":" + node.id
    if isinstance(node, ast.Attribute):
        if _is_state_motion_power(node):
            return 1.0
        return DYNAMIC + ":" + _dotted_name(node)
    if isinstance(node, ast.Tuple):
        return tuple(_eval_node(item) for item in node.elts)
    if isinstance(node, ast.List):
        return [_eval_node(item) for item in node.elts]
    if isinstance(node, ast.Dict):
        return {
            _eval_node(key): _eval_node(value)
            for key, value in zip(node.keys, node.values)
            if key is not None
        }
    if isinstance(node, ast.UnaryOp):
        value = _eval_node(node.operand)
        if isinstance(node.op, ast.USub):
            return -float(value)
        if isinstance(node.op, ast.UAdd):
            return float(value)
    if isinstance(node, ast.BinOp):
        left = _eval_node(node.left)
        right = _eval_node(node.right)
        if isinstance(node.op, ast.Mult):
            return float(left) * float(right)
        if isinstance(node.op, ast.Div):
            return float(left) / float(right)
        if isinstance(node.op, ast.Add):
            return left + right
        if isinstance(node.op, ast.Sub):
            return float(left) - float(right)
    raise ValueError("unsupported AST value: %s" % ast.dump(node, include_attributes=False))


def _as_float(node):
    value = _eval_node(node)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("not numeric")
    return float(value)


def _as_vector(node):
    value = _eval_node(node)
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        raise ValueError("not a 3-vector")
    return tuple(float(item) for item in value)


def _camel_to_suffix(name):
    text = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", name).lower()
    text = re.sub(r"([a-z])([0-9]+)$", r"\1_\2", text)
    return text


def _bound_state_id(class_node):
    # Codex 2026-08-09: 实体专属状态类按 BindMobState 的状态 ID 对齐动画，不依赖类名前缀。
    for decorator in class_node.decorator_list:
        if not isinstance(decorator, ast.Call) or _dotted_name(decorator.func).rsplit(".", 1)[-1] != "BindMobState":
            continue
        if len(decorator.args) < 2:
            continue
        try:
            state_id = _eval_node(decorator.args[1])
        except ValueError:
            continue
        if isinstance(state_id, str):
            return state_id
    return None


def _read_json(path):
    with path.open("r", encoding="utf-8") as stream:
        return json.load(stream)


def _find_method(class_node, name):
    for node in class_node.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return node
    return None


def _read_window_assignments(method):
    values = {}
    if method is None:
        return values
    for node in ast.walk(method):
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if (
                isinstance(target, ast.Attribute)
                and isinstance(target.value, ast.Name)
                and target.value.id == "self"
                and target.attr in WINDOW_FIELDS
            ):
                try:
                    values[target.attr] = _as_float(node.value)
                except ValueError:
                    values[target.attr] = DYNAMIC
    return values


def _dict_assignments(method):
    result = []
    for node in ast.walk(method):
        if not isinstance(node, ast.Assign) or not isinstance(node.value, ast.Dict):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name):
                try:
                    value = _eval_node(node.value)
                except ValueError:
                    value = {}
                result.append((node.lineno, target.id, value))
    return sorted(result)


def _dict_before(assignments, name, line):
    candidates = [value for lineno, key, value in assignments if key == name and lineno < line]
    return dict(candidates[-1]) if candidates else {}


def _module_constants(tree):
    result = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        try:
            value = _eval_node(node.value)
        except (TypeError, ValueError):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id.isupper():
                result[target.id] = value
    return result


def _static_value(node, constants):
    if isinstance(node, ast.Name) and node.id in constants:
        return constants[node.id]
    return _eval_node(node)


def _parse_state_class(class_node, state_id=None, constants=None):
    constants = constants or {}
    init_method = _find_method(class_node, "__init__")
    start_method = _find_method(class_node, "onStart")
    if start_method is None:
        return None
    assignments = _dict_assignments(start_method)
    motions = []
    attacks = []
    effects = []
    base_on_start = []
    calls = sorted(
        (node for node in ast.walk(start_method) if isinstance(node, ast.Call)),
        key=lambda item: (item.lineno, item.col_offset),
    )
    for order, call in enumerate(calls):
        call_name = _dotted_name(call.func)
        short_name = call_name.rsplit(".", 1)[-1]
        if short_name == "onStart" and call_name != "self.onStart":
            owner = call_name.rsplit(".", 1)[0]
            if owner and owner != "self":
                base_on_start.append(owner)
        if call_name == "SetMoveMotion" and len(call.args) >= 2:
            try:
                motions.append({
                    "time": 0.0,
                    "direction": _as_vector(call.args[0]),
                    "power": _as_float(call.args[1]),
                    "line": call.lineno,
                    "order": order,
                })
            except ValueError:
                pass
        if short_name == "ScheduleRootMotionTicks" and call.args:
            try:
                timeline = _static_value(call.args[0], constants)
                for tick_order, item in enumerate(timeline):
                    motions.append({
                        "time": float(item[0]),
                        "direction": tuple(float(value) for value in item[1]),
                        "power": float(item[2]),
                        "integration": "tick_delta",
                        "line": call.lineno,
                        "order": order + (tick_order + 1) / 1000.0,
                    })
            except (TypeError, ValueError):
                pass
        if short_name != "StateAnim_CreateTimer" or len(call.args) < 2:
            continue
        try:
            delay = _as_float(call.args[0])
        except ValueError:
            continue
        callback = _dotted_name(call.args[1]).rsplit(".", 1)[-1]
        if callback in ("SetMoveMotion", "SetLocalVectorMoveMotion") and len(call.args) >= 5:
            try:
                motions.append({
                    "time": delay,
                    "direction": _as_vector(call.args[3]),
                    "power": _as_float(call.args[4]),
                    "local": callback == "SetLocalVectorMoveMotion",
                    "line": call.lineno,
                    "order": order,
                })
            except ValueError:
                pass
            continue
        if callback == "CreateAttack" and len(call.args) >= 4:
            if isinstance(call.args[3], ast.Name):
                data = _dict_before(assignments, call.args[3].id, call.lineno)
            else:
                try:
                    data = _eval_node(call.args[3])
                except ValueError:
                    data = {}
            attacks.append({"time": delay, "data": data, "line": call.lineno})
            continue
        if callback in KNOWN_EFFECTS or callback.startswith("PlayPunch"):
            payload = []
            for item in call.args[3:]:
                try:
                    payload.append(_eval_node(item))
                except ValueError:
                    payload.append(DYNAMIC)
            effects.append({"time": delay, "kind": callback, "args": payload, "line": call.lineno})

    for call in calls:
        call_name = _dotted_name(call.func)
        short_name = call_name.rsplit(".", 1)[-1]
        if short_name != "ScheduleSwordSoulEffect" or len(call.args) < 4:
            continue
        try:
            delay = _as_float(call.args[0])
            method = _eval_node(call.args[2])
            payload = _eval_node(call.args[3])
        except ValueError:
            continue
        effects.append({"time": delay, "kind": method, "args": payload, "line": call.lineno})

    motions.sort(key=lambda item: (item["time"], item["line"], item["order"]))
    attacks.sort(key=lambda item: (item["time"], item["line"]))
    effects.sort(key=lambda item: (item["time"], item["line"]))
    return {
        "class": class_node.name,
        "state_id": state_id,
        "suffix": state_id[len("fight_"):] if state_id and state_id.startswith("fight_") else _camel_to_suffix(class_node.name),
        "bases": [_dotted_name(item) for item in class_node.bases],
        "windows": _read_window_assignments(init_method),
        "motions": motions,
        "attacks": attacks,
        "effects": effects,
        "base_on_start": sorted(set(base_on_start)),
    }


def _keyframe_value(value, prefer="post"):
    if isinstance(value, dict):
        value = value.get(prefer, value.get("post", value.get("pre")))
    if isinstance(value, (int, float)):
        return (float(value),) * 3
    if isinstance(value, list) and len(value) == 3 and all(isinstance(item, (int, float)) for item in value):
        return tuple(float(item) for item in value)
    return None


def _root_summary(animation, axis_signs):
    position = animation.get("bones", {}).get("root_move", {}).get("position")
    if not isinstance(position, dict):
        return {"keyframes": 0, "delta": None, "mapped_delta": None, "has_catmullrom": False}
    keyframes = []
    has_catmullrom = False
    for raw_time, raw_value in position.items():
        value = _keyframe_value(raw_value)
        if value is None:
            continue
        if isinstance(raw_value, dict) and raw_value.get("lerp_mode") == "catmullrom":
            has_catmullrom = True
        keyframes.append((float(raw_time), value))
    keyframes.sort()
    if not keyframes:
        return {"keyframes": 0, "delta": None, "mapped_delta": None, "has_catmullrom": has_catmullrom}
    first = keyframes[0][1]
    last = keyframes[-1][1]
    delta = tuple(last[index] - first[index] for index in range(3))
    mapped = tuple(delta[index] * axis_signs[index] for index in range(3))
    return {
        "keyframes": len(keyframes),
        "first_time": keyframes[0][0],
        "last_time": keyframes[-1][0],
        "first": first,
        "last": last,
        "delta": delta,
        "mapped_delta": mapped,
        "has_catmullrom": has_catmullrom,
    }


def _animation_rate(expression):
    if not expression:
        return 1.0
    match = re.fullmatch(
        r"(?:query|q)\.anim_time\s*\+\s*(?:query|q)\.delta_time\s*\*\s*([0-9]+(?:\.[0-9]+)?)",
        expression.strip(),
    )
    return float(match.group(1)) if match else None


def _dedupe_motion_schedule(motions):
    result = []
    for item in motions:
        clean = {key: value for key, value in item.items() if key not in ("line", "order")}
        if result and abs(result[-1]["time"] - clean["time"]) < 1e-9:
            result[-1] = clean
        else:
            result.append(clean)
    return result


def _integrate_motion(schedule, end_time):
    net = [0.0, 0.0, 0.0]
    for index, item in enumerate(schedule):
        direction = item["direction"]
        length = math.sqrt(sum(value * value for value in direction))
        unit = tuple(value / length for value in direction) if length else (0.0, 0.0, 0.0)
        if item.get("integration") == "tick_delta":
            for axis in range(3):
                net[axis] += unit[axis] * item["power"]
            continue
        start = item["time"]
        end = schedule[index + 1]["time"] if index + 1 < len(schedule) else end_time
        duration = max(0.0, min(end, end_time) - max(start, 0.0))
        for axis in range(3):
            net[axis] += unit[axis] * item["power"] * duration
    return tuple(net)


def _vector_length(value):
    return math.sqrt(sum(item * item for item in value))


def _classify_hitbox(data):
    attack_type = data.get("AttackType", "Round")
    if attack_type != "Round":
        return str(attack_type).lower()
    rotate = data.get("rotate", (0, 0, 0))
    high = float(data.get("high", 1.2) or 0.0)
    radians = float(data.get("radians", 90.0) or 0.0)
    high_type = data.get("high_type", "all")
    if (
        isinstance(rotate, (list, tuple))
        and len(rotate) >= 1
        and abs(float(rotate[0])) >= 80.0
        and high_type == "up"
        and high >= 8.0
    ):
        return "ground_corridor"
    if radians >= 350.0:
        return "radial"
    if radians >= 240.0:
        return "wide_sector"
    return "front_sector"


def _append_warning(warnings, code, message, severity="medium"):
    warnings.append({"code": code, "severity": severity, "message": message})


def _analyze_move(state, animation_name, animation, bb_animation, motion_scale, axis_signs, min_segment):
    warnings = []
    windows = state["windows"]
    end_time = windows.get("StateAnimTime")
    if not isinstance(end_time, (int, float)):
        end_time = float(animation.get("animation_length", 0.0) or 0.0)
        _append_warning(warnings, "missing-state-anim-time", "缺少可解析的 StateAnimTime。", "high")
    schedule = _dedupe_motion_schedule(state["motions"])
    motion_net = _integrate_motion(schedule, float(end_time)) if schedule else (0.0, 0.0, 0.0)
    tick_root_motion = any(item.get("integration") == "tick_delta" for item in schedule)
    effective_motion_scale = 1.0 / 16.0 if tick_root_motion else motion_scale
    root = _root_summary(animation, axis_signs)
    implied_scale = None
    root_error = None
    mapped = root.get("mapped_delta")
    if mapped is not None:
        denominator = sum(value * value for value in mapped)
        if denominator:
            implied_scale = sum(motion_net[index] * mapped[index] for index in range(3)) / denominator
            expected = tuple(value * effective_motion_scale for value in mapped)
            root_error = _vector_length(tuple(motion_net[index] - expected[index] for index in range(3)))
    if schedule:
        if abs(schedule[0]["time"]) > 1e-9:
            _append_warning(warnings, "motion-missing-zero-start", "位移表没有从 0 秒开始。")
        last = schedule[-1]
        if abs(last["time"] - float(end_time)) > 1e-6 or last["power"] != 0.0:
            _append_warning(warnings, "motion-missing-terminal-zero", "StateAnimTime 没有最终位移清零。", "high")
        for left, right in zip(schedule, schedule[1:]):
            if left.get("integration") != "tick_delta" and right["time"] - left["time"] < min_segment - 1e-9:
                _append_warning(
                    warnings,
                    "motion-dense-segment",
                    "位移段 %.4f～%.4f 短于 %.3fs。" % (left["time"], right["time"], min_segment),
                )
        for item in schedule:
            length = _vector_length(item["direction"])
            if item["power"] > 0.0 and abs(length - 1.0) > 0.003:
                _append_warning(warnings, "motion-direction-not-normalized", "非零位移方向未归一化：%r。" % (item["direction"],))
    if mapped is not None and root_error is not None and root_error > max(0.001, _vector_length(mapped) * effective_motion_scale * 0.02):
        _append_warning(warnings, "root-motion-integral-drift", "服务器位移积分与 root_move×scale 的误差为 %.6f。" % root_error, "high")

    expression = animation.get("anim_time_update", "")
    rate = _animation_rate(expression)
    animation_length = float(animation.get("animation_length", 0.0) or 0.0)
    visual_duration = animation_length / rate if rate else None
    if rate is None:
        _append_warning(warnings, "unparsed-anim-time-update", "无法静态解析 anim_time_update：%r。" % expression, "high")
    elif abs(visual_duration - float(end_time)) > 0.0001:
        _append_warning(
            warnings,
            "animation-duration-mismatch",
            "动画有效时长 %.5fs 与 StateAnimTime %.5fs 不一致。" % (visual_duration, end_time),
            "high",
        )
    if bb_animation is not None:
        bb_length = float(bb_animation.get("length", 0.0) or 0.0)
        if abs(bb_length - animation_length) > 0.0001:
            _append_warning(warnings, "bbmodel-length-drift", "BBModel 与导出动画长度不一致。", "high")
        bb_clock = bb_animation.get("anim_time_update") or ""
        # Codex 2026-08-09: BBModel 可留空并由确定性导出器按状态时长注入；只有显式源时钟冲突才算漂移。
        if bb_clock and bb_clock != (expression or ""):
            _append_warning(warnings, "bbmodel-rate-drift", "BBModel 与导出动画 anim_time_update 不一致。", "high")

    attack_time = windows.get("AttackTime")
    latest_create = max((item["time"] for item in state["attacks"]), default=0.0)
    attack_close = None
    if isinstance(attack_time, (int, float)):
        attack_close = max(float(attack_time), latest_create) + 0.05
    analyzed_attacks = []
    for item in state["attacks"]:
        data = dict(item["data"])
        hit_time = float(data.get("hit_time", 0.0) or 0.0)
        declared_end = item["time"] + hit_time
        actual_end = min(declared_end, float(end_time))
        if attack_close is not None:
            actual_end = min(actual_end, attack_close)
        effective_scan = max(0.0, actual_end - item["time"])
        if isinstance(attack_time, (int, float)) and item["time"] > float(attack_time) + 1e-9:
            _append_warning(warnings, "attack-created-after-attack-time", "攻击盒 %.3fs 晚于 AttackTime %.3fs。" % (item["time"], attack_time), "high")
        if hit_time - effective_scan > 1e-6:
            _append_warning(
                warnings,
                "attack-scan-clipped",
                "%.3fs 创建的攻击盒声明扫描 %.3fs，实际最多 %.3fs。" % (item["time"], hit_time, effective_scan),
            )
        analyzed_attacks.append({
            "time": item["time"],
            "data": data,
            "shape": _classify_hitbox(data),
            "declared_scan": hit_time,
            "effective_scan": effective_scan,
        })

    ordered_windows = [windows.get(name) for name in WINDOW_FIELDS]
    if all(isinstance(value, (int, float)) for value in ordered_windows):
        if any(left > right for left, right in zip(ordered_windows, ordered_windows[1:])):
            _append_warning(warnings, "state-window-order", "状态窗口不满足 Attack<=UnControl<=Keep<=Anim。", "high")

    analyzed_effects = []
    hit_times = [item["time"] for item in analyzed_attacks]
    for item in state["effects"]:
        nearest_delta = None
        if hit_times:
            nearest = min(hit_times, key=lambda value: abs(value - item["time"]))
            nearest_delta = item["time"] - nearest
        analyzed_effects.append({
            "time": item["time"],
            "kind": item["kind"],
            "args": item["args"],
            "nearest_attack_delta": nearest_delta,
        })
    if state["base_on_start"]:
        _append_warning(
            warnings,
            "inherited-on-start-not-expanded",
            "调用共享 onStart：%s；本报告未展开其无条件声音/镜头/VFX。" % ", ".join(state["base_on_start"]),
        )

    return {
        "class": state["class"],
        "suffix": state["suffix"],
        "animation": animation_name,
        "windows": windows,
        "animation_length": animation_length,
        "anim_time_update": expression,
        "anim_rate": rate,
        "visual_duration": visual_duration,
        "motions": schedule,
        "motion_net": motion_net,
        "motion_integration": "tick_delta" if tick_root_motion else "piecewise_velocity",
        "effective_motion_scale": effective_motion_scale,
        "root": root,
        "implied_motion_scale": implied_scale,
        "root_integral_error": root_error,
        "attacks": analyzed_attacks,
        "effects": analyzed_effects,
        "base_on_start": state["base_on_start"],
        "attack_state_close": attack_close,
        "warnings": warnings,
    }


def _find_animation(animations, suffix):
    matches = [(name, value) for name, value in animations.items() if name.endswith("." + suffix)]
    if len(matches) == 1:
        return matches[0]
    return None, None


def _find_bbmodel(project_root, name):
    matches = [path for path in project_root.rglob(name) if ".build" not in path.parts]
    if len(matches) != 1:
        raise ValueError("BBModel %s expected once, found %d: %r" % (name, len(matches), matches))
    return matches[0]


def analyze(entity_python, animation_json, bbmodel=None, class_names=None, motion_scale=0.00527, axis_signs=(1.0, 1.0, -1.0), min_segment=0.08):
    source = entity_python.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(entity_python))
    constants = _module_constants(tree)
    animations = _read_json(animation_json).get("animations", {})
    bb_animations = {}
    if bbmodel is not None:
        bb_animations = {
            item.get("name"): item
            for item in _read_json(bbmodel).get("animations", [])
            if item.get("name")
        }
    selected = set(class_names or [])
    moves = []
    missing = []
    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue
        state_id = _bound_state_id(node)
        if selected and node.name not in selected:
            continue
        if not selected:
            bound_attack = bool(
                state_id
                and state_id.startswith("fight_attack_")
                and state_id != "fight_attack_defense"
            )
            legacy_attack = node.name.startswith("Attack") and node.name != "AttackDefense"
            if not bound_attack and not legacy_attack:
                continue
        state = _parse_state_class(node, state_id, constants)
        if state is None:
            continue
        animation_suffix = state["suffix"]
        if animation_suffix.startswith("budge_"):
            # Codex 2026-08-09: 小闪状态在控制器中复用同方向 dodge 动画，审计时沿用该映射。
            animation_suffix = "dodge_" + animation_suffix[len("budge_"):]
        animation_name, animation = _find_animation(animations, animation_suffix)
        if animation is None:
            missing.append({
                "class": node.name,
                "suffix": state["suffix"],
                "animation_suffix": animation_suffix,
            })
            continue
        moves.append(_analyze_move(
            state,
            animation_name,
            animation,
            bb_animations.get(animation_name),
            motion_scale,
            axis_signs,
            min_segment,
        ))
    return {
        "entity_python": str(entity_python),
        "animation_json": str(animation_json),
        "bbmodel": str(bbmodel) if bbmodel else None,
        "motion_scale": motion_scale,
        "axis_signs": axis_signs,
        "moves": moves,
        "missing_animations": missing,
    }


def _fmt(value, digits=4):
    if value is None:
        return "—"
    if isinstance(value, float):
        return ("%%.%df" % digits) % value
    return str(value)


def render_markdown(report):
    lines = [
        "# Mob move alignment audit",
        "",
        "- Entity: `%s`" % report["entity_python"],
        "- Animation: `%s`" % report["animation_json"],
        "- BBModel: `%s`" % (report["bbmodel"] or "not provided"),
        "- Motion scale: `%s`" % _fmt(report["motion_scale"], 5),
        "- Axis signs: `%s`" % (report["axis_signs"],),
        "",
        "| Move | Windows A/U/K/Anim | Hits | VFX | Motion net | Implied scale | Warnings |",
        "|---|---|---|---|---|---:|---:|",
    ]
    for move in report["moves"]:
        windows = move["windows"]
        window_text = "/".join(_fmt(windows.get(name), 2) for name in WINDOW_FIELDS)
        hit_text = ", ".join("%.2f:%s" % (item["time"], item["shape"]) for item in move["attacks"]) or "—"
        effect_text = ", ".join("%.2f:%s" % (item["time"], item["kind"]) for item in move["effects"]) or "—"
        net_text = "(%s)" % ",".join(_fmt(value, 4) for value in move["motion_net"])
        lines.append(
            "| `%s` | %s | %s | %s | %s | %s | %d |"
            % (
                move["suffix"],
                window_text,
                hit_text,
                effect_text,
                net_text,
                _fmt(move["implied_motion_scale"], 6),
                len(move["warnings"]),
            )
        )
    for move in report["moves"]:
        lines.extend(["", "## %s" % move["suffix"], ""])
        lines.append(
            "Animation length `%s`, rate `%s`, visual duration `%s`, attack-state close `%s`."
            % (
                _fmt(move["animation_length"]),
                _fmt(move["anim_rate"]),
                _fmt(move["visual_duration"]),
                _fmt(move["attack_state_close"]),
            )
        )
        if move["attacks"]:
            lines.extend(["", "Attacks:", ""])
            for item in move["attacks"]:
                data = item["data"]
                lines.append(
                    "- `%.3fs` %s, range=%s, radians=%s, high=%s/%s, rotate=%s, offset=%s, scan=%s→%s."
                    % (
                        item["time"],
                        item["shape"],
                        data.get("range", 2.5),
                        data.get("radians", 90),
                        data.get("high", 1.2),
                        data.get("high_type", "all"),
                        data.get("rotate", (0, 0, 0)),
                        data.get("offset", (0, 0, 0)),
                        _fmt(item["declared_scan"], 3),
                        _fmt(item["effective_scan"], 3),
                    )
                )
        if move["effects"]:
            lines.extend(["", "VFX:", ""])
            for item in move["effects"]:
                lines.append(
                    "- `%.3fs` %s, nearest hit delta `%s`."
                    % (item["time"], item["kind"], _fmt(item["nearest_attack_delta"], 3))
                )
        if move["warnings"]:
            lines.extend(["", "Warnings:", ""])
            for warning in move["warnings"]:
                lines.append("- **%s/%s**: %s" % (warning["severity"], warning["code"], warning["message"]))
    if report["missing_animations"]:
        lines.extend(["", "## Missing animations", ""])
        for item in report["missing_animations"]:
            lines.append("- `%s` -> `*.%s`" % (item["class"], item["suffix"]))
    return "\n".join(lines) + "\n"


def _parse_axis_signs(value):
    parts = [float(item.strip()) for item in value.split(",")]
    if len(parts) != 3 or any(item not in (-1.0, 1.0) for item in parts):
        raise argparse.ArgumentTypeError("axis signs must be three comma-separated +1/-1 values")
    return tuple(parts)


def main(argv=None):
    _configure_stdout()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--entity-python", required=True, type=pathlib.Path)
    parser.add_argument("--animation-json", required=True, type=pathlib.Path)
    parser.add_argument("--bbmodel", type=pathlib.Path)
    parser.add_argument("--bbmodel-name", help="Find one BBModel by ASCII filename below the current project.")
    parser.add_argument("--class", dest="class_names", action="append")
    parser.add_argument("--motion-scale", type=float, default=0.00527)
    parser.add_argument("--axis-signs", type=_parse_axis_signs, default=(1.0, 1.0, -1.0))
    parser.add_argument("--min-segment", type=float, default=0.08)
    parser.add_argument("--format", choices=("markdown", "json"), default="markdown")
    args = parser.parse_args(argv)
    bbmodel = args.bbmodel
    if args.bbmodel_name:
        bbmodel = _find_bbmodel(pathlib.Path.cwd(), args.bbmodel_name)
    report = analyze(
        args.entity_python,
        args.animation_json,
        bbmodel=bbmodel,
        class_names=args.class_names,
        motion_scale=args.motion_scale,
        axis_signs=args.axis_signs,
        min_segment=args.min_segment,
    )
    if args.format == "json":
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(render_markdown(report), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
