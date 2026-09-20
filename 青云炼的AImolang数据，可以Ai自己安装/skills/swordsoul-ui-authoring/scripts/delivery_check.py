from __future__ import print_function

from pathlib import Path

from _common import json_print, project_root, read_text
from audit_ui import build_audit


REQUIRED_RUNTIME = [
    "src/SwordSoul_NewERA_B/SwordSoulFightScripts/QingYunModLibs/UIAnimation.py",
    "src/SwordSoul_NewERA_B/SwordSoulFightScripts/QingYunModLibs/ConfigUI/Binding.py",
    "src/SwordSoul_NewERA_B/SwordSoulFightScripts/QingYunModLibs/ConfigUI/ConfigScreen.py",
    "src/SwordSoul_NewERA_B/SwordSoulFightScripts/QingYunModLibs/ConfigUI/DataSource.py",
    "src/SwordSoul_NewERA_B/SwordSoulFightScripts/QingYunModLibs/ConfigUI/Layout.py",
    "src/SwordSoul_NewERA_B/SwordSoulFightScripts/QingYunModLibs/ConfigUI/Renderer.py",
    "src/SwordSoul_NewERA_B/SwordSoulFightScripts/QingYunModLibs/ConfigUI/Schema.py",
    "src/SwordSoul_NewERA_B/SwordSoulFightScripts/QingYunModLibs/ConfigUI/StateStore.py",
    "src/SwordSoul_NewERA_B/SwordSoulFightScripts/QingYunModLibs/ConfigUI/Template.py",
    "src/SwordSoul_NewERA_B/SwordSoulFightScripts/UISystem/ConfigUI/SettingScreen.py",
    "src/SwordSoul_NewERA_B/SwordSoulFightScripts/UISystem/ConfigUI/SettingStore.py",
    "src/SwordSoul_NewERA_B/SwordSoulFightScripts/UISystem/ConfigUI/Templates.py",
]

REQUIRED_KNOWLEDGE = [
    ".codex/skills/swordsoul-ui-authoring/SKILL.md",
    ".codex/agents/common/ui/qingyun-config-ui-agent.md",
    ".codex/agents/project/ui/ui-architecture-agent.md",
    ".codex/agents/project/ui/ui-setting-agent.md",
    ".codex/agents/project/ui/ui-verification-agent.md",
]


def check_delivery():
    root = project_root()
    findings = []
    for item in REQUIRED_RUNTIME + REQUIRED_KNOWLEDGE:
        if not (root / item).is_file():
            findings.append("missing required file: " + item)

    main_setting = read_text(root / "src/SwordSoul_NewERA_B/SwordSoulFightScripts/UISystem/MainSetting.py")
    if "class BaseScreenRenderCls(BaseSWSSettingScreen):" not in main_setting:
        findings.append("BaseScreenRenderCls does not inherit BaseSWSSettingScreen")
    if "return BaseSWSSettingScreen.render(self)" not in main_setting:
        findings.append("BaseScreenRenderCls lacks explicit hot-reload render delegation")
    if "**Options" not in main_setting:
        findings.append("legacy addCompToConfig does not accept extension options")

    trail = read_text(root / "src/SwordSoul_NewERA_B/SwordSoulFightScripts/UISystem/TrailScreen.py")
    if "class BaseScreenRenderCls" in trail:
        findings.append("TrailScreen still contains a duplicate BaseScreenRenderCls")

    migrated = ("SkinUI.py", "CapeUI.py", "EmoteUI.py")
    for file_name in migrated:
        path = root / "src/SwordSoul_NewERA_B/SwordSoulFightScripts/UISystem" / file_name
        text = read_text(path)
        if "def render(self):" in text:
            findings.append(file_name + " still overrides the complete render flow")
        if "LayoutConfig" not in text or "SelectionCard" not in text:
            findings.append(file_name + " is not migrated to LayoutConfig + SelectionCard")

    audit = build_audit()
    findings.extend(audit["blocking_findings"])
    return {
        "status": "pass" if not findings else "findings",
        "findings": findings,
        "required_runtime_files": len(REQUIRED_RUNTIME),
        "required_knowledge_files": len(REQUIRED_KNOWLEDGE),
        "offline_audit_status": audit["status"],
        "migrated_reference_screens": list(migrated),
    }


def main():
    result = check_delivery()
    json_print(result)
    if result["findings"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
