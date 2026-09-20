# coding=utf-8
import ast
import copy
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[4]
ENDERMAN_PATH = (
    PROJECT_ROOT
    / "src"
    / "SwordSoul_NewERA_B"
    / "SwordSoulMobFightScripts"
    / "Entities"
    / "EndermanMob.py"
)


class FakeMobCombatStateType(object):
    ATTACK = "attack"
    SNEAKING = "sneaking"
    DEFENSE = "defense"
    DODGE = "dodge"


class FakeVanillaFightMobEntity(object):
    def __init__(self, entityId):
        self.entityId = entityId
        self.hard_enabled = True
        self.soft_enabled = False
        self.components = {
            "minecraft:teleport": {
                "random_teleports": True,
                "max_random_teleport_time": 30,
                "random_teleport_cube": [32, 32, 32],
                "target_distance": 16,
                "target_teleport_chance": 0.05,
                "light_teleport_chance": 0.05,
            },
            "minecraft:movement": {"value": 0.3},
        }
        self.removed = []
        self.added = []
        self.fail_remove = None
        self.fail_add = None
        self.tick_count = 0
        self.destroyed = False

    def _get_effective_components(self):
        return self.components

    def _snapshot_active_components(self, componentMap, components):
        return dict(
            (name, copy.deepcopy(components[name]))
            for name in componentMap
            if name in components
        )

    def _remove_native_components(self, componentMap):
        result = True
        for name in componentMap:
            self.removed.append(name)
            if name == self.fail_remove:
                result = False
                continue
            self.components.pop(name, None)
        return result

    def _restore_native_components(self, componentMap):
        result = True
        for name, data in componentMap.items():
            self.added.append((name, copy.deepcopy(data)))
            if name == self.fail_add:
                result = False
                continue
            self.components[name] = copy.deepcopy(data)
        return result

    def initialize_runtime(self):
        return True

    def set_hard_switch(self, enabled):
        self.hard_enabled = bool(enabled)
        if not self.hard_enabled:
            self.soft_enabled = False
        return True

    def set_soft_switch(self, enabled):
        self.soft_enabled = bool(enabled) and self.hard_enabled
        return True

    def tick(self, tick_index=0, alive=None):
        del tick_index, alive
        self.tick_count += 1
        return True

    def destroy(self):
        self.destroyed = True
        return True


def LoadEndermanClass():
    source = ENDERMAN_PATH.read_text(encoding="utf-8-sig")
    tree = ast.parse(source)
    classNode = next(
        node for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "EndermanMob"
    )
    classNode = copy.deepcopy(classNode)
    classNode.decorator_list = []
    module = ast.Module(body=[classNode], type_ignores=[])
    ast.fix_missing_locations(module)
    namespace = {
        "VanillaFightMobEntity": FakeVanillaFightMobEntity,
        "MobCombatStateType": FakeMobCombatStateType,
        "ENDERMAN_ENTITY_TYPE": "minecraft:enderman",
    }
    exec(compile(module, str(ENDERMAN_PATH), "exec"), namespace)
    return namespace["EndermanMob"]


def main():
    EndermanMob = LoadEndermanClass()
    teleportName = "minecraft:teleport"
    originalTeleport = copy.deepcopy(FakeVanillaFightMobEntity("source").components[teleportName])

    # Codex 2026-08-10: 瞬移不得再随软战斗模式的原生控制表恢复。
    assert teleportName not in EndermanMob.NativeControlComponentMap
    assert teleportName not in EndermanMob.NativeSnapshotRequiredComponents

    defaultEnabled = EndermanMob("default_enabled")
    assert defaultEnabled.set_hard_switch(True) is True
    assert defaultEnabled.hard_enabled is True
    assert teleportName not in defaultEnabled.components
    assert defaultEnabled.components["minecraft:movement"] == {"value": 0.3}
    assert defaultEnabled.NativeTeleportSuppressed is True
    assert defaultEnabled.initialize_runtime() is True
    assert defaultEnabled.removed == [teleportName]

    assert defaultEnabled.set_hard_switch(False) is True
    assert defaultEnabled.hard_enabled is False
    assert defaultEnabled.components[teleportName] == originalTeleport
    assert defaultEnabled.NativeTeleportSnapshotReady is False
    assert defaultEnabled.NativeTeleportSuppressed is False

    assert defaultEnabled.set_hard_switch(True) is True
    assert teleportName not in defaultEnabled.components
    assert defaultEnabled.NativeTeleportSuppressed is True

    failedRemove = EndermanMob("failed_remove")
    failedRemove.fail_remove = teleportName
    assert failedRemove.set_hard_switch(True) is False
    assert failedRemove.hard_enabled is True
    assert failedRemove.components[teleportName] == originalTeleport
    assert failedRemove.NativeTeleportSnapshotReady is True
    failedRemove.fail_remove = None
    assert failedRemove.tick(1, True) is True
    assert teleportName not in failedRemove.components
    assert failedRemove.NativeTeleportSuppressed is True

    softGate = EndermanMob("soft_gate")
    softGate.fail_remove = teleportName
    assert softGate.set_hard_switch(True) is False
    assert softGate.set_soft_switch(True) is False
    assert softGate.soft_enabled is False
    softGate.fail_remove = None
    assert softGate.set_soft_switch(True) is True
    assert softGate.soft_enabled is True
    assert softGate.NativeTeleportSuppressed is True

    failedRestore = EndermanMob("failed_restore")
    assert failedRestore.set_hard_switch(True) is True
    failedRestore.fail_add = teleportName
    assert failedRestore.set_hard_switch(False) is False
    assert failedRestore.hard_enabled is False
    assert failedRestore.NativeTeleportSnapshotReady is True
    assert failedRestore.NativeTeleportSuppressed is True
    failedRestore.fail_add = None
    assert failedRestore.tick(1, True) is True
    assert failedRestore.components[teleportName] == originalTeleport
    assert failedRestore.NativeTeleportSnapshotReady is False

    destroyProbe = EndermanMob("destroy")
    assert destroyProbe.set_hard_switch(True) is True
    assert destroyProbe.destroy() is True
    assert destroyProbe.destroyed is True
    assert destroyProbe.components[teleportName] == originalTeleport

    print("enderman teleport hard-switch regression passed")


if __name__ == "__main__":
    main()
