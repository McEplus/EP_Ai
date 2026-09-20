# coding=utf-8
"""铁傀儡、坚守者、劫掠兽、末影人和蜘蛛的控制器代理前缀回归。"""

import ast
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[4]
STATIC_PATH = (
    PROJECT_ROOT
    / "src"
    / "SwordSoul_NewERA_B"
    / "SwordSoulMobFightScripts"
    / "Render"
    / "StaticRenderConfig.py"
)


# Codex 2026-08-10: 原版控制器按 client entity 短名列出，直接动画不进入本表。
TARGETS = {
    "IronGolemStaticRenderConfig": {
        "native": {
            "move_controller": "controller.animation.iron_golem.move",
            "arm_controller": "controller.animation.iron_golem.arm_movement",
        },
        "core": ("iron_golem_fight_controller", "controller.animation.fight_iron_golem"),
        "direct_scripts": {"look_at_target"},
    },
    "WardenStaticRenderConfig": {
        "native": {
            "shiver_controller": "controller.animation.warden.shiver",
            "sniff_controller": "controller.animation.warden.sniff",
            "roar_controller": "controller.animation.warden.roar",
            "melee_attack_controller": "controller.animation.warden.melee_attacking",
            "sonic_boom_controller": "controller.animation.warden.sonic_boom",
        },
        "core": ("warden_fight_controller", "controller.animation.fight_warden"),
        "direct_scripts": {
            "base_pose", "move", "bob", "emerge", "dig", "look_at_target", "swimming",
        },
    },
    "RavagerStaticRenderConfig": {
        "native": {
            "move": "controller.animation.ravager.move",
            "head": "controller.animation.ravager.head_movement",
        },
        "core": ("ravager_fight_controller", "controller.animation.fight_ravager"),
        "direct_scripts": set(),
    },
    "EndermanStaticRenderConfig": {
        "native": {
            "look_at_target": "controller.animation.humanoid.look_at_target",
            "move": "controller.animation.humanoid.move",
            "attack": "controller.animation.humanoid.attack",
            "bob": "controller.animation.humanoid.bob",
            "base_pose": "controller.animation.enderman.base_pose",
            "carrying": "controller.animation.enderman.carrying",
            "scary_face": "controller.animation.enderman.scary_face",
        },
        "core": ("enderman_fight_controller", "controller.animation.fight_enderman"),
        "direct_scripts": set(),
    },
    "SpiderStaticRenderConfig": {
        "native": {
            "move": "controller.animation.spider.move",
        },
        "core": ("spider_fight_controller", "controller.animation.fight_spider"),
        "direct_scripts": set(),
    },
}


def ReadStaticClasses():
    Tree = ast.parse(STATIC_PATH.read_text(encoding="utf-8-sig"))
    Result = {}
    for Node in Tree.body:
        if not isinstance(Node, ast.ClassDef) or Node.name not in TARGETS:
            continue
        Assignments = {}
        for Item in Node.body:
            if not isinstance(Item, ast.Assign) or not isinstance(Item.targets[0], ast.Name):
                continue
            try:
                Assignments[Item.targets[0].id] = ast.literal_eval(Item.value)
            except (ValueError, TypeError):
                continue
        Result[Node.name] = Assignments
    return Result


def Main():
    StaticClasses = ReadStaticClasses()
    assert set(StaticClasses) == set(TARGETS)
    ControllerCount = 0
    for ClassName, Expected in TARGETS.items():
        Assignments = StaticClasses[ClassName]
        ControllerMap = Assignments["animation_controller"]
        ScriptMap = Assignments["script_animate"]
        assert all(Key.startswith("c_") for Key in ControllerMap), (ClassName, ControllerMap)
        assert set(ControllerMap) <= set(ScriptMap), (ClassName, set(ControllerMap) - set(ScriptMap))

        for ShortName, ResourceName in Expected["native"].items():
            ProxyName = "c_" + ShortName
            assert ControllerMap.get(ProxyName) == ResourceName, (ClassName, ProxyName)
            assert "!query.mod.fight" in ScriptMap.get(ProxyName, ""), (ClassName, ProxyName)
            assert ShortName not in ScriptMap, (ClassName, ShortName)

        CoreShortName, CoreResourceName = Expected["core"]
        CoreProxyName = "c_" + CoreShortName
        assert ControllerMap.get(CoreProxyName) == CoreResourceName, ClassName
        assert ScriptMap.get(CoreProxyName) == "", ClassName
        assert set(Assignments["remove_animation_controller"]) == {
            "controller__" + ShortName for ShortName in Expected["native"]
        }

        for ShortName in Expected["direct_scripts"]:
            assert ShortName in Assignments["animation"], (ClassName, ShortName)
            assert ShortName in ScriptMap, (ClassName, ShortName)
            assert "c_" + ShortName not in Assignments["animation"], (ClassName, ShortName)
        ControllerCount += len(ControllerMap)

    print(
        "vanilla controller proxy prefix checks passed: mobs=%d controllers=%d"
        % (len(TARGETS), ControllerCount)
    )


if __name__ == "__main__":
    Main()
