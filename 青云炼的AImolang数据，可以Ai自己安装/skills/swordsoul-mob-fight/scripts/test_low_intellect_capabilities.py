# coding=utf-8
"""低智力 AI 基础招式能力边界回归检查。"""

import ast
import runpy
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[4]
AI_ROOT = (
    PROJECT_ROOT
    / "src"
    / "SwordSoul_NewERA_B"
    / "SwordSoulMobFightScripts"
    / "AI"
)
INTELLECT_PATH = AI_ROOT / "Intellect.py"
CORE_PATH = AI_ROOT / "Core.py"
SKILL_PATH = AI_ROOT / "Skill.py"
SENSE_PATH = AI_ROOT / "Sense.py"

BLOCKED_LOW_SKILLS = {
    "charge_hold",
    "charge_release",
    "charge_attack",
    "charge_attack_2",
}


class FakeMob(object):
    aiIntellect = "low"
    aiIntellectParams = None


class FakeMidMob(object):
    aiIntellect = "mid"
    aiIntellectParams = None


class FakeSkill(object):
    def __init__(self, SkillId):
        self.skillId = SkillId


def ReadAssignment(Tree, Name):
    for Node in Tree.body:
        if not isinstance(Node, ast.Assign):
            continue
        if any(isinstance(Target, ast.Name) and Target.id == Name for Target in Node.targets):
            return ast.literal_eval(Node.value)
    raise AssertionError("missing assignment: %s" % Name)


def ReadFunction(Tree, Name):
    for Node in Tree.body:
        if isinstance(Node, ast.FunctionDef) and Node.name == Name:
            return Node
    raise AssertionError("missing function: %s" % Name)


def ReadClassFunction(Tree, ClassName, FunctionName):
    ClassNode = next(
        Node for Node in Tree.body
        if isinstance(Node, ast.ClassDef) and Node.name == ClassName
    )
    return next(
        Node for Node in ClassNode.body
        if isinstance(Node, ast.FunctionDef) and Node.name == FunctionName
    )


def ReadCandidateIds():
    Tree = ast.parse(SKILL_PATH.read_text(encoding="utf-8-sig"))
    Result = set()
    for Node in ast.walk(Tree):
        if not isinstance(Node, ast.Call) or not Node.args:
            continue
        if not isinstance(Node.func, ast.Name) or Node.func.id != "AISkillCandidate":
            continue
        try:
            Result.add(ast.literal_eval(Node.args[0]))
        except (ValueError, TypeError):
            continue
    return Result


def BuildCapabilityHarness():
    Tree = ast.parse(CORE_PATH.read_text(encoding="utf-8-sig"))
    Namespace = {
        "_SKILL_CAPABILITY_MAP": ReadAssignment(Tree, "_SKILL_CAPABILITY_MAP"),
        "_SKILL_TACTIC_MAP": ReadAssignment(Tree, "_SKILL_TACTIC_MAP"),
    }
    FunctionNode = ReadFunction(Tree, "_skill_intellect_allowed")
    ModuleNode = ast.Module(body=[FunctionNode], type_ignores=[])
    ast.fix_missing_locations(ModuleNode)
    exec(compile(ModuleNode, str(CORE_PATH), "exec"), Namespace)
    return Namespace


def BuildPredictedRangeHarness():
    Tree = ast.parse(SENSE_PATH.read_text(encoding="utf-8-sig"))
    FunctionNode = ReadClassFunction(Tree, "MobSense", "predicted_skill_max_range")
    ModuleNode = ast.Module(body=[FunctionNode], type_ignores=[])
    ast.fix_missing_locations(ModuleNode)
    Namespace = {}
    exec(compile(ModuleNode, str(SENSE_PATH), "exec"), Namespace)
    return Namespace["predicted_skill_max_range"]


def Main():
    # Codex 2026-08-04: 验证低智力开放疾跑攻击，但整条地面蓄力链仍从候选池硬过滤。
    IntellectModule = runpy.run_path(str(INTELLECT_PATH))
    LowIntellect = IntellectModule["resolve_intellect"](FakeMob())
    MidIntellect = IntellectModule["resolve_intellect"](FakeMidMob())
    DefaultIntellect = IntellectModule["AIIntellectParams"]()
    Harness = BuildCapabilityHarness()
    CapabilityMap = Harness["_SKILL_CAPABILITY_MAP"]
    IsAllowed = Harness["_skill_intellect_allowed"]

    assert BLOCKED_LOW_SKILLS <= ReadCandidateIds(), "blocked skill id missing from candidates"
    assert BLOCKED_LOW_SKILLS <= set(CapabilityMap), CapabilityMap
    assert CapabilityMap["sprint_attack"] == "allowSprintAttack"
    for SkillId in BLOCKED_LOW_SKILLS:
        assert CapabilityMap[SkillId] == "allowGroundChargeAttack", SkillId
    assert LowIntellect.allowSprintAttack
    assert not LowIntellect.allowGroundChargeAttack
    assert LowIntellect.attackRange == 3.6
    assert LowIntellect.commonAttackPredictedRangeBonus == 0.6
    assert MidIntellect.attackRange == 3.0
    assert MidIntellect.commonAttackPredictedRangeBonus == 0.0
    # Codex 2026-08-04: low 禁止两种完美反应，mid 只保留完美格挡。
    assert not LowIntellect.allowPerfectDefense
    assert not LowIntellect.allowPerfectDodge
    assert MidIntellect.allowPerfectDefense
    assert not MidIntellect.allowPerfectDodge
    assert DefaultIntellect.allowPerfectDefense
    assert DefaultIntellect.allowPerfectDodge
    for SkillId in BLOCKED_LOW_SKILLS:
        assert not IsAllowed(LowIntellect, FakeSkill(SkillId)), SkillId
        assert IsAllowed(DefaultIntellect, FakeSkill(SkillId)), SkillId
    assert IsAllowed(LowIntellect, FakeSkill("sprint_attack"))
    assert IsAllowed(LowIntellect, FakeSkill("normal_attack"))

    class FakeProfile(object):
        firstHitTime = 0.3

        def predicted_max_range(self, TargetApproach, aggressive=False):
            assert aggressive
            return 3.2 + TargetApproach

    class FakeSense(object):
        def __init__(self, Intellect):
            self.mob = type("Mob", (), {"ai_core": type("Core", (), {"intellect": Intellect})()})()

        def estimate_target_approach_distance(self, LeadTime):
            assert 0.25 <= LeadTime <= 1.2
            return 0.2

    CommonAttack = FakeSkill("common_attack")
    CommonAttack.rangeProfile = FakeProfile()
    SprintAttack = FakeSkill("sprint_attack")
    SprintAttack.rangeProfile = FakeProfile()
    PredictRange = BuildPredictedRangeHarness()
    assert abs(PredictRange(FakeSense(LowIntellect), CommonAttack) - 4.0) < 0.0001
    assert abs(PredictRange(FakeSense(MidIntellect), CommonAttack) - 3.4) < 0.0001
    assert abs(PredictRange(FakeSense(LowIntellect), SprintAttack) - 3.4) < 0.0001
    print(
        "low intellect capability boundary valid: blocked=%d attack_range=%.1f common_bonus=%.1f sprint=on"
        % (len(BLOCKED_LOW_SKILLS), LowIntellect.attackRange, LowIntellect.commonAttackPredictedRangeBonus)
    )


if __name__ == "__main__":
    Main()
