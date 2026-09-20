# coding=utf-8
"""低智力 AI 共享进攻与尝试格挡权重回归检查。"""

import ast
import runpy
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[4]
MOB_SCRIPT_ROOT = PROJECT_ROOT / "src" / "SwordSoul_NewERA_B" / "SwordSoulMobFightScripts"
CORE_PATH = MOB_SCRIPT_ROOT / "AI" / "Core.py"
INTELLECT_PATH = MOB_SCRIPT_ROOT / "AI" / "Intellect.py"
ZOMBIE_PATH = MOB_SCRIPT_ROOT / "Entities" / "ZombieMob.py"


def ReadClassNode(PathValue, ClassName):
    Tree = ast.parse(PathValue.read_text(encoding="utf-8-sig"))
    return next(
        Node for Node in Tree.body
        if isinstance(Node, ast.ClassDef) and Node.name == ClassName
    )


def ReadMethod(PathValue, ClassName, MethodName):
    ClassNode = ReadClassNode(PathValue, ClassName)
    return next(
        Node for Node in ClassNode.body
        if isinstance(Node, ast.FunctionDef) and Node.name == MethodName
    )


def ReadCalledMethodNames(PathValue, ClassName, MethodName):
    MethodNode = ReadMethod(PathValue, ClassName, MethodName)
    return {
        Node.func.attr for Node in ast.walk(MethodNode)
        if isinstance(Node, ast.Call) and isinstance(Node.func, ast.Attribute)
    }


def BuildHarness(Name, SourceClassName, MethodNames, Namespace=None):
    Methods = [ReadMethod(CORE_PATH, SourceClassName, MethodName) for MethodName in MethodNames]
    ClassNode = ast.ClassDef(
        name=Name,
        bases=[ast.Name(id="object", ctx=ast.Load())],
        keywords=[],
        body=Methods,
        decorator_list=[],
    )
    ModuleNode = ast.Module(body=[ClassNode], type_ignores=[])
    ast.fix_missing_locations(ModuleNode)
    Result = dict(Namespace or {})
    exec(compile(ModuleNode, str(CORE_PATH), "exec"), Result)
    return Result[Name]


class ValueObject(object):
    def __init__(self, **Values):
        self.__dict__.update(Values)


class LowMob(object):
    aiIntellect = "low"
    aiIntellectParams = None


class MidMob(object):
    aiIntellect = "mid"
    aiIntellectParams = None


class FakeDecision(object):
    def __init__(self, Skill, Score, Reason):
        self.skill = Skill
        self.score = Score
        self.reason = Reason


class FixedRandom(object):
    value = 0.0

    @classmethod
    def random(cls):
        return cls.value


def Main():
    # Codex 2026-08-04: 权重必须来自 low 智力预设，僵尸类不得再持有专属副本。
    IntellectModule = runpy.run_path(str(INTELLECT_PATH))
    ResolveIntellect = IntellectModule["resolve_intellect"]
    LowIntellect = ResolveIntellect(LowMob())
    AnotherLowIntellect = ResolveIntellect(LowMob())
    MidIntellect = ResolveIntellect(MidMob())
    UtilityBias = LowIntellect.skillUtilityBiasMap
    ReactionWeight = LowIntellect.normalAttackReactionWeightMap
    assert UtilityBias["common_attack"] > 0.0
    # Codex 2026-08-07: 成功格挡不再是主动候选，低智力表也不得保留对应收益键。
    assert "defense_common" not in UtilityBias
    assert UtilityBias["defense_try"] < 0.0
    assert ReactionWeight["attack"] > ReactionWeight["defense"]
    assert ReactionWeight["attack"] > ReactionWeight["dodge"]
    assert abs(sum(ReactionWeight.values()) - 1.0) < 0.000001
    assert AnotherLowIntellect.skillUtilityBiasMap == UtilityBias
    assert AnotherLowIntellect.normalAttackReactionWeightMap == ReactionWeight
    assert AnotherLowIntellect.skillUtilityBiasMap is not UtilityBias
    assert AnotherLowIntellect.normalAttackReactionWeightMap is not ReactionWeight
    assert MidIntellect.skillUtilityBiasMap == {}
    assert MidIntellect.normalAttackReactionWeightMap == {}

    ZombieClass = ReadClassNode(ZOMBIE_PATH, "ZombieMob")
    ZombieAssignments = {
        Target.id for Node in ZombieClass.body if isinstance(Node, ast.Assign)
        for Target in Node.targets if isinstance(Target, ast.Name)
    }
    assert "AIUtilityBiasMap" not in ZombieAssignments
    assert "AINormalAttackReactionWeightMap" not in ZombieAssignments
    assert "_score_intellect_skill_bias" in ReadCalledMethodNames(
        CORE_PATH, "UtilityEvaluator", "_score_skill"
    )
    assert "_pick_intellect_normal_attack_reaction_decision" in ReadCalledMethodNames(
        CORE_PATH, "MobAICore", "_try_normal_attack_reaction_pool_decision"
    )

    UtilityHarness = BuildHarness(
        "UtilityHarness",
        "UtilityEvaluator",
        ("_score_intellect_skill_bias",),
    )()
    LowRuntimeMob = ValueObject(ai_core=ValueObject(intellect=LowIntellect))
    MidRuntimeMob = ValueObject(ai_core=ValueObject(intellect=MidIntellect))
    assert UtilityHarness._score_intellect_skill_bias(
        LowRuntimeMob, ValueObject(skillId="common_attack")
    ) == 24.0
    assert UtilityHarness._score_intellect_skill_bias(
        LowRuntimeMob, ValueObject(skillId="defense_try")
    ) == -18.0
    assert UtilityHarness._score_intellect_skill_bias(
        MidRuntimeMob, ValueObject(skillId="common_attack")
    ) == 0.0

    ReactionHarness = BuildHarness(
        "ReactionHarness",
        "MobAICore",
        ("_pick_intellect_normal_attack_reaction_decision",),
        {"random": FixedRandom, "AIDecision": FakeDecision},
    )()
    Attack = ValueObject(skillId="common_attack")
    Defense = ValueObject(skillId="defense_try")
    Dodge = ValueObject(skillId="dodge_left")
    Skills = [Attack, Defense, Dodge]
    ReactionHarness.mob = LowRuntimeMob
    ReactionHarness.intellect = LowIntellect
    ReactionHarness.effectFilter = ValueObject(filter=lambda Mob, Sense, Candidates: Candidates)
    ReactionHarness._pick_skill_by_id = lambda Usable, SkillId: next(
        (Skill for Skill in Usable if Skill.skillId == SkillId), None
    )
    ReactionHarness._pick_emergency_skill = lambda Usable, Kind: Defense if Kind == "defense" else Dodge
    for Roll, ExpectedSkill, ExpectedReason in (
        (0.10, Attack, "normal_reaction_intellect_attack"),
        (0.70, Defense, "normal_reaction_intellect_defense"),
        (0.90, Dodge, "normal_reaction_intellect_dodge"),
    ):
        FixedRandom.value = Roll
        Decision = ReactionHarness._pick_intellect_normal_attack_reaction_decision(ValueObject(), Skills)
        assert Decision.skill is ExpectedSkill, (Roll, Decision.skill.skillId)
        assert Decision.reason == ExpectedReason, (Roll, Decision.reason)
    ReactionHarness.intellect = MidIntellect
    assert ReactionHarness._pick_intellect_normal_attack_reaction_decision(ValueObject(), Skills) is None
    print(
        "low intellect combat weights valid: attack=%.2f defense=%.2f dodge=%.2f"
        % (ReactionWeight["attack"], ReactionWeight["defense"], ReactionWeight["dodge"])
    )


if __name__ == "__main__":
    Main()
