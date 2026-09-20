# coding=utf-8
"""全量生物招式归零恢复策略回归；仅尸壳和青云保留完成品生命周期。"""

import ast
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[4]
ENTITY_ROOT = PROJECT_ROOT / "src" / "SwordSoul_NewERA_B" / "SwordSoulMobFightScripts" / "Entities"
AI_CORE_PATH = ENTITY_ROOT.parent / "AI" / "Core.py"
POLICY_NAMES = (
    "ActiveTargetHoldsFightMode",
    "PassiveSoftFightHoldEnabled",
    "ExitFightModeOnStateNone",
)
IMMEDIATE_POLICY = (False, False, True)
LEGACY_POLICY = (True, True, False)
LEGACY_ENTITY_TYPES = {"minecraft:husk", "arris:qingyun"}


def LiteralAssignments(Nodes):
    Result = {}
    for Node in Nodes:
        if not isinstance(Node, ast.Assign) or len(Node.targets) != 1:
            continue
        Target = Node.targets[0]
        if not isinstance(Target, ast.Name):
            continue
        try:
            Result[Target.id] = ast.literal_eval(Node.value)
        except (ValueError, TypeError):
            pass
    return Result


def BuildInventory():
    Classes = {}
    Registered = []
    for PathValue in sorted(ENTITY_ROOT.glob("*.py")):
        Tree = ast.parse(PathValue.read_text(encoding="utf-8-sig"), str(PathValue))
        ModuleValues = LiteralAssignments(Tree.body)
        for Node in Tree.body:
            if not isinstance(Node, ast.ClassDef):
                continue
            IsRelevant = Node.name in (
                "SwordSoulMobEntity", "VanillaFightMobEntity", "SimpleAttackMob",
            )
            EntityType = None
            for Decorator in Node.decorator_list:
                if not isinstance(Decorator, ast.Call) or not Decorator.args:
                    continue
                Name = ast.unparse(Decorator.func)
                if Name != "MobEntityRegistry.Entity":
                    continue
                ValueNode = Decorator.args[0]
                if isinstance(ValueNode, ast.Name):
                    EntityType = ModuleValues.get(ValueNode.id)
                else:
                    EntityType = ast.literal_eval(ValueNode)
                IsRelevant = True
            if not IsRelevant:
                continue
            # BaseMob 中历史上存在同名占位声明，后定义的完整类才是运行时类。
            Classes[Node.name] = {
                "base": ast.unparse(Node.bases[0]) if Node.bases else None,
                "values": LiteralAssignments(Node.body),
                "path": PathValue,
            }
            if EntityType:
                Registered.append((EntityType, Node.name))
    return Classes, Registered


def ResolvePolicy(Classes, ClassName):
    Values = []
    for PolicyName in POLICY_NAMES:
        CurrentName = ClassName
        while CurrentName:
            Current = Classes[CurrentName]
            if PolicyName in Current["values"]:
                Values.append(Current["values"][PolicyName])
                break
            CurrentName = Current["base"] if Current["base"] in Classes else None
        else:
            raise AssertionError("missing policy: %s.%s" % (ClassName, PolicyName))
    return tuple(Values)


def Main():
    Classes, Registered = BuildInventory()
    assert Registered
    assert ResolvePolicy(Classes, "SimpleAttackMob") == IMMEDIATE_POLICY
    assert ResolvePolicy(Classes, "VanillaFightMobEntity") == IMMEDIATE_POLICY
    BaseSource = (ENTITY_ROOT / "BaseMob.py").read_text(encoding="utf-8-sig")
    assert 'self.fight_controller.get_state_id() != "fight_none"' in BaseSource
    AICoreSource = AI_CORE_PATH.read_text(encoding="utf-8-sig")
    AITree = ast.parse(AICoreSource, str(AI_CORE_PATH))
    DecideNode = next(
        Node for ClassNode in AITree.body
        if isinstance(ClassNode, ast.ClassDef) and ClassNode.name == "MobAICore"
        for Node in ClassNode.body
        if isinstance(Node, ast.FunctionDef) and Node.name == "decide"
    )
    ExecuteNode = next(
        Node for ClassNode in AITree.body
        if isinstance(ClassNode, ast.ClassDef) and ClassNode.name == "MobAICore"
        for Node in ClassNode.body
        if isinstance(Node, ast.FunctionDef) and Node.name == "execute_decision"
    )
    assert "hold_soft_fight_mode" not in ast.unparse(DecideNode)
    assert "self.mob.input_command" in ast.unparse(ExecuteNode)
    SeenTypes = set()
    for EntityType, ClassName in Registered:
        assert EntityType not in SeenTypes, EntityType
        SeenTypes.add(EntityType)
        Expected = LEGACY_POLICY if EntityType in LEGACY_ENTITY_TYPES else IMMEDIATE_POLICY
        Actual = ResolvePolicy(Classes, ClassName)
        assert Actual == Expected, (EntityType, ClassName, Actual, Expected)

    assert LEGACY_ENTITY_TYPES <= SeenTypes
    assert len(SeenTypes) >= 17
    print(
        "mob fight_none restore policy checks passed: entities=%d immediate=%d legacy=%d"
        % (len(SeenTypes), len(SeenTypes - LEGACY_ENTITY_TYPES), len(LEGACY_ENTITY_TYPES))
    )


if __name__ == "__main__":
    Main()
