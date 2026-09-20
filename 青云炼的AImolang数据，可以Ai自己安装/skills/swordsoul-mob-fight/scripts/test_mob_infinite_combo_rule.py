# coding=utf-8
"""生物无限连招规则与玩家僵直保护隔离回归。"""

import ast
import copy
import textwrap
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[4]
SWS_ROOT = PROJECT_ROOT / "src" / "SwordSoul_NewERA_B" / "SwordSoulFightScripts"
MOB_ROOT = PROJECT_ROOT / "src" / "SwordSoul_NewERA_B" / "SwordSoulMobFightScripts"
GENERAL_SCREEN_PATH = SWS_ROOT / "UISystem" / "GeneralScreen.py"
SETTING_DATA_PATH = SWS_ROOT / "UISystem" / "SettingData.py"
FIGHT_SERVER_PATH = SWS_ROOT / "FightSystem" / "FightServer.py"
FIGHT_CLIENT_PATH = SWS_ROOT / "FightSystem" / "FightClient.py"
MOB_CONTROLLER_PATH = MOB_ROOT / "Combat" / "FightController.py"


def ReadSource(PathValue):
    return PathValue.read_text(encoding="utf-8-sig")


def ExtractMethod(PathValue, MethodName):
    """从仍含 Python 2 print 的运行时文件中只解析目标方法。"""
    Source = ReadSource(PathValue)
    StartMarker = "    def %s(" % MethodName
    Start = Source.index(StartMarker)
    EndCandidates = [
        Position for Position in (
            Source.find("\n    def ", Start + 1),
            Source.find("\n    @", Start + 1),
        )
        if Position >= 0
    ]
    End = min(EndCandidates) if EndCandidates else len(Source)
    Tree = ast.parse(textwrap.dedent(Source[Start:End]))
    MethodNode = next(Node for Node in Tree.body if isinstance(Node, ast.FunctionDef))
    MethodNode.decorator_list = []
    return MethodNode


def CompileMethod(PathValue, MethodName, Namespace=None):
    MethodNode = copy.deepcopy(ExtractMethod(PathValue, MethodName))
    ModuleNode = ast.fix_missing_locations(ast.Module(body=[MethodNode], type_ignores=[]))
    Result = dict(Namespace or {})
    exec(compile(ModuleNode, str(PathValue), "exec"), Result)
    return Result[MethodName]


class ValueObject(object):
    def __init__(self, **Values):
        self.__dict__.update(Values)


class MobHitHarness(object):
    def __init__(self, StiffStack):
        self.FightStateUnBreak = False
        self.ReactionCount = 0
        self.mob = ValueObject(
            entityId="mob-target",
            command_translator=ValueObject(
                CancelStiffSystem=False,
                StiffProtectState=False,
                StiffStack=StiffStack,
                MaxStiffValue=0.5,
                HitType="none",
                StiffTime=0.0,
            ),
        )

    def get_state_type(self):
        return "none"

    def get_state_id(self):
        return "fight_none"

    def is_unbreakable_execute_break_time(self):
        return False

    def _is_entity_on_ground(self, EntityId):
        return True

    def ResolveReactionState(self, StateId):
        return StateId

    def TryReactionState(self, RequestedStateId, ResolvedStateId, Changes, Request=None):
        self.ReactionCount += 1
        for Key, Value in Changes.items():
            setattr(self.mob.command_translator, Key, Value)
        return True


class FakeQueryVariable(object):
    def EvalMolangExpression(self, Expression):
        return {"value": False}


class FakeClientComp(object):
    @staticmethod
    def CreateQueryVariable(EntityId):
        return FakeQueryVariable()


class PlayerHitHarness(object):
    def __init__(self):
        self.FightStateUnBreak = False
        self.CancelStiffSystem = False
        self.StiffProtectState = False
        self.StiffStack = 0.25
        self.MaxStiffValue = 0.5
        self.MobInfiniteCombo = True
        self.HitType = "none"
        self.StiffTime = 0.0
        self.CancelCount = 0

    def getStateType(self):
        return "none"

    def getStateId(self):
        return "fight_none"

    def CheckArmorLevel(self, AttackLevel):
        return False

    def BackState(self, Source, Data):
        return True

    def getFightStateMachine(self):
        return ValueObject(CancelCD=self._CancelCD)

    def _CancelCD(self):
        self.CancelCount += 1


def AssertSettingChain():
    GeneralSource = ReadSource(GENERAL_SCREEN_PATH)
    SettingSource = ReadSource(SETTING_DATA_PATH)
    ServerSource = ReadSource(FIGHT_SERVER_PATH)
    MobSource = ReadSource(MOB_CONTROLLER_PATH)
    for Snippet in (
        '"id": "MobInfiniteCombo"',
        '"label": "无限连招"',
        '"bind_func": self.onMobInfiniteCombo',
        "def onMobInfiniteCombo(self, State):",
    ):
        assert Snippet in GeneralSource, Snippet
    ConfigStart = GeneralSource.index('"id": "MobInfiniteCombo"')
    ConfigEnd = GeneralSource.index("            },", ConfigStart)
    InfiniteComboConfig = GeneralSource[ConfigStart:ConfigEnd]
    assert '"default_value": False' in InfiniteComboConfig
    assert '"auto_save": False' in InfiniteComboConfig
    # Codex 2026-08-11: 页面顺序固定为无限怒气、无限连招、武器耐久保护。
    assert (
        GeneralSource.index('"id": "AllPower"')
        < ConfigStart
        < GeneralSource.index('"id": "KeepWeaponDurability"')
    )
    for Snippet in (
        "self.MobInfiniteCombo = False",
        'self.SetLocalConfig("MobInfiniteCombo", True, False)',
        'CallServer("UpdateRuleSetting", [playerId, "MobInfiniteCombo", State])',
    ):
        assert Snippet in SettingSource, Snippet
    for Snippet in (
        '"MobInfiniteCombo": False',
        'self.GetRuleSetting("MobInfiniteCombo")',
        'GetEngineTypeStr(OnHurtId) != "minecraft:player"',
        '"infinite_combo": bool(',
    ):
        assert Snippet in ServerSource, Snippet
    assert 'hitParam.get("infinite_combo", False)' in MobSource
    assert "newStiffStack = 0.0 if infiniteCombo else oldStiffStack + stiffValue" in MobSource


def AssertMobRuleBehavior():
    OnHitCommon = CompileMethod(
        MOB_CONTROLLER_PATH,
        "OnHitCommon",
        {"mob_trace": lambda *Args: None},
    )
    BaseHit = {
        "onSpace": False,
        "fading": True,
        "hitTime": 1.0,
        "stiff_value": 0.1,
    }

    Normal = MobHitHarness(0.25)
    # Codex 2026-08-11: 缺省命中参数必须等价于规则关闭，完整保留旧保护阈值。
    assert OnHitCommon(Normal, dict(BaseHit)) is True
    assert abs(Normal.mob.command_translator.StiffStack - 0.35) < 0.000001
    assert Normal.mob.command_translator.StiffTime == 0.0

    Infinite = MobHitHarness(0.25)
    for _ in range(3):
        assert OnHitCommon(Infinite, dict(BaseHit, infinite_combo=True)) is True
        assert Infinite.mob.command_translator.StiffStack == 0.0
        assert Infinite.mob.command_translator.StiffTime == 1.0
    assert Infinite.ReactionCount == 3


def AssertPlayerProtectionUnchanged():
    OnHitCommon = CompileMethod(
        FIGHT_CLIENT_PATH,
        "OnHitCommon",
        {
            "ClientComp": FakeClientComp,
            "playerId": "player-target",
            "GetStiffResetReason": lambda *Args: "",
            "GetStiffTutorialResult": lambda *Args: "stiff_accumulated",
            "NotifyTutorialFightResult": lambda *Args: None,
        },
    )
    Player = PlayerHitHarness()
    assert OnHitCommon(Player, {
        "onSpace": False,
        "fading": True,
        "hitTime": 1.0,
        "stiff_value": 0.1,
        # Codex 2026-08-11: 即使扩展参数意外送达玩家，玩家累计逻辑也必须完全忽略它。
        "infinite_combo": True,
    }) is None
    assert abs(Player.StiffStack - 0.35) < 0.000001
    assert Player.StiffTime == 0.0
    assert Player.HitType == "light"
    assert Player.CancelCount == 1


def Main():
    AssertSettingChain()
    AssertMobRuleBehavior()
    AssertPlayerProtectionUnchanged()
    print("mob infinite combo rule valid: setting=ok mob=unlimited player=protected")


if __name__ == "__main__":
    Main()
