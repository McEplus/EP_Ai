from __future__ import print_function

from _common import git_changed_files, json_print


def classify(path):
    lower = path.lower()
    surfaces = []
    if "/uisystem/" in lower or "/configui/" in lower:
        surfaces.append("python_ui")
    if "/ui/" in lower and lower.endswith(".json"):
        surfaces.append("resource_ui_json")
    if "/textures/ui/" in lower:
        surfaces.append("ui_texture")
    if lower.endswith("uiconfig.py"):
        surfaces.append("control_paths")
    if lower.endswith("settingdata.py"):
        surfaces.append("setting_persistence")
    if lower.endswith("control.py"):
        surfaces.append("hud_or_input")
    if path.startswith(".codex/"):
        surfaces.append("development_knowledge_or_tool")
    return surfaces


def main():
    changed = []
    for path in git_changed_files():
        surfaces = classify(path)
        if surfaces:
            changed.append({"file": path, "surfaces": surfaces})
    json_print({
        "ui_related_changes": changed,
        "manual_checks": [
            "Confirm source changes were not copied into .build/dist.",
            "For runtime UI changes, use the analogous in-game screen and verify render/unRender.",
            "For settings, verify default, persistence, apply callback, and consumer behavior.",
        ],
    })


if __name__ == "__main__":
    main()

