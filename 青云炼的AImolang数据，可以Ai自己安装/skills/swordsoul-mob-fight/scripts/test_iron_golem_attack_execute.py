# coding=utf-8
"""校验铁傀儡处决攻击的 root_move、出伤与烟尘时序。"""

import ast
import json
import math
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[4]
ENTITY_PATH = PROJECT_ROOT / "src" / "SwordSoul_NewERA_B" / "SwordSoulMobFightScripts" / "Entities" / "IronGolemMob.py"
ANIMATION_PATH = PROJECT_ROOT / "src" / "SwordSoul_NewERA_R" / "animations" / "mob" / "iron_golem" / "fight_iron_golem.animation.json"
ANIMATION_NAME = "animation.fight_iron_golem.attack_execute"


def AttributePath(Node):
    if isinstance(Node, ast.Name):
        return Node.id
    if isinstance(Node, ast.Attribute):
        Prefix = AttributePath(Node.value)
        return "%s.%s" % (Prefix, Node.attr) if Prefix else Node.attr
    return ""


def MotionPowerFactor(Node):
    assert isinstance(Node, ast.BinOp) and isinstance(Node.op, ast.Mult)
    if AttributePath(Node.left) == "self.State_MotionPower":
        return float(ast.literal_eval(Node.right))
    assert AttributePath(Node.right) == "self.State_MotionPower"
    return float(ast.literal_eval(Node.left))


def ReadAttackExecuteDefinition():
    Tree = ast.parse(ENTITY_PATH.read_text(encoding="utf-8"))
    ClassNode = next(Node for Node in Tree.body if isinstance(Node, ast.ClassDef) and Node.name == "AttackExecute")
    InitNode = next(Node for Node in ClassNode.body if isinstance(Node, ast.FunctionDef) and Node.name == "__init__")
    StartNode = next(Node for Node in ClassNode.body if isinstance(Node, ast.FunctionDef) and Node.name == "onStart")

    Timings = {}
    for Node in InitNode.body:
        if not isinstance(Node, ast.Assign) or not isinstance(Node.targets[0], ast.Attribute):
            continue
        Timings[Node.targets[0].attr] = ast.literal_eval(Node.value)

    Motions = []
    AttackTimes = []
    SmokeCalls = []
    for Node in ast.walk(StartNode):
        if not isinstance(Node, ast.Call):
            continue
        CallPath = AttributePath(Node.func)
        if CallPath == "SetMoveMotion":
            Motions.append((0.0, ast.literal_eval(Node.args[0]), MotionPowerFactor(Node.args[1])))
            continue
        if CallPath == "self.StateAnim_CreateTimer":
            CallbackPath = AttributePath(Node.args[1])
            if CallbackPath == "SetMoveMotion":
                Motions.append((
                    float(ast.literal_eval(Node.args[0])),
                    ast.literal_eval(Node.args[3]),
                    MotionPowerFactor(Node.args[4]),
                ))
            elif CallbackPath == "self.PlayerRootController.CreateAttack":
                AttackTimes.append(float(ast.literal_eval(Node.args[0])))
            continue
        if CallPath == "self.ScheduleSwordSoulEffect":
            SmokeCalls.append(Node)

    return Timings, sorted(Motions), sorted(AttackTimes), SmokeCalls


def ReadRootMoveFrames():
    Data = json.loads(ANIMATION_PATH.read_text(encoding="utf-8"))
    Animations = Data["animations"]
    Animation = Animations[ANIMATION_NAME]
    Position = Animation["bones"]["root_move"]["position"]
    Frames = []
    for TimeKey, RawValue in Position.items():
        if isinstance(RawValue, dict):
            Value = RawValue.get("post", RawValue.get("pre"))
        else:
            Value = RawValue
        Frames.append((float(TimeKey), tuple(float(Component) for Component in Value)))
    return Animation, sorted(Frames), len(Animations)


def AssertAttackExecute():
    Timings, Motions, AttackTimes, SmokeCalls = ReadAttackExecuteDefinition()
    assert Timings["AttackTime"] == 1.3
    assert Timings["UnControlTime"] == 1.4
    assert Timings["StateKeepTime"] == 1.5
    assert Timings["StateAnimTime"] == 1.8
    assert AttackTimes == [0.58, 1.17]

    assert len(SmokeCalls) == 1
    SmokeCall = SmokeCalls[0]
    assert float(ast.literal_eval(SmokeCall.args[0])) == 0.6
    assert ast.literal_eval(SmokeCall.args[1]) == "AttackEffectSystem"
    assert ast.literal_eval(SmokeCall.args[2]) == "DirtSmoke"
    assert AttributePath(SmokeCall.args[3].elts[0]) == "self.playerId"
    assert ast.literal_eval(SmokeCall.args[3].elts[1]) == (0, 0, 0)

    Animation, Frames, AnimationCount = ReadRootMoveFrames()
    assert Animation.get("loop") == "hold_on_last_frame"
    assert float(Animation["animation_length"]) == 2.0
    assert len(Frames) == 8
    assert len(Motions) == len(Frames)

    TimeScale = Timings["StateAnimTime"] / float(Animation["animation_length"])
    MovingScaleRatios = []
    for Index in range(len(Frames) - 1):
        Time, Position = Frames[Index]
        NextTime, NextPosition = Frames[Index + 1]
        MotionTime, MotionDirection, MotionPower = Motions[Index]
        assert abs(MotionTime - Time*TimeScale) <= 0.0051

        Delta = (
            NextPosition[0] - Position[0],
            NextPosition[1] - Position[1],
            -(NextPosition[2] - Position[2]),
        )
        Distance = math.sqrt(sum(Value*Value for Value in Delta))
        if Distance == 0.0:
            assert MotionDirection == (0, 0, 0)
            assert MotionPower == 0.0
            continue

        ExpectedDirection = tuple(Value/Distance for Value in Delta)
        for Actual, Expected in zip(MotionDirection, ExpectedDirection):
            assert abs(float(Actual) - Expected) <= 0.006
        # Codex 2026-08-04: 速度按实际两位小数调度窗口校验，覆盖 1.125 秒关键帧舍入为 1.13 的情况。
        ScheduledDuration = Motions[Index + 1][0] - MotionTime
        MovingScaleRatios.append((Distance/ScheduledDuration)/MotionPower)

    assert abs(Motions[-1][0] - Timings["StateAnimTime"]) < 0.000001
    assert Motions[-1][1:] == ((0, 0, 0), 0.0)
    assert all(185.0 <= Ratio <= 200.0 for Ratio in MovingScaleRatios), MovingScaleRatios
    return AnimationCount, len(Frames), len(MovingScaleRatios)


def Main():
    AnimationCount, FrameCount, MovingSegmentCount = AssertAttackExecute()
    print(
        "iron golem attack_execute valid: animations=%d root_frames=%d moving_segments=%d"
        % (AnimationCount, FrameCount, MovingSegmentCount)
    )


if __name__ == "__main__":
    Main()
