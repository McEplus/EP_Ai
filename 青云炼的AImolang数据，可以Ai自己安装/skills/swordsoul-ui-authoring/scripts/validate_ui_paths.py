from __future__ import print_function

import ast
import json
from pathlib import Path

from _common import behavior_ui_root, json_print, read_text, relative, resource_ui_root


CLASS_UI_FILE = {
    "ControlConfig": "Control.json",
    "MainSettingConfig": "MainSetting.json",
    "GeneralScreenConfig": "MainSetting.json",
    "DetailScreenConfig": "MainSetting.json",
    "ItemChooseScreenConfig": "MainSetting.json",
    "AnnouncementConfig": "Announcement.json",
    "TutorialScreenConfig": "TutorialScreen.json",
    "OnboardingScreenConfig": "OnboardingScreen.json",
    "TrailScreenConfig": "TrailScreen.json",
    "EditControlConfig": "EditControlScreen.json",
    "EmojiButtonConfig": "EmojiButton.json",
    "EmojiUiConfig": "EmojiUi.json",
    "AnimateScreenConfig": "AnimateScreen.json",
}


def eval_value(node, local_values, class_values):
    if hasattr(ast, "Constant") and isinstance(node, ast.Constant):
        return node.value
    if hasattr(ast, "Str") and isinstance(node, ast.Str):
        return node.s
    if isinstance(node, ast.Name):
        return local_values.get(node.id)
    if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
        return class_values.get(node.value.id, {}).get(node.attr)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left = eval_value(node.left, local_values, class_values)
        right = eval_value(node.right, local_values, class_values)
        if isinstance(left, str) and isinstance(right, str):
            return left + right
    return None


def extract_config_paths():
    config_path = behavior_ui_root() / "UIConfig.py"
    tree = ast.parse(read_text(config_path), filename=str(config_path))
    class_values = {}
    records = []
    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue
        local_values = {}
        for statement in node.body:
            if not isinstance(statement, ast.Assign) or len(statement.targets) != 1:
                continue
            target = statement.targets[0]
            if not isinstance(target, ast.Name):
                continue
            value = eval_value(statement.value, local_values, class_values)
            if value is not None:
                local_values[target.id] = value
                if isinstance(value, str) and value.startswith("/"):
                    records.append({"class": node.name, "name": target.id, "path": value})
        class_values[node.name] = local_values
    return records


def collect_control_paths(data):
    paths = set()
    inherited_roots = set()

    def walk(node, parent_path):
        if not isinstance(node, dict):
            return
        controls = node.get("controls", [])
        if not isinstance(controls, list):
            return
        for entry in controls:
            if not isinstance(entry, dict):
                continue
            for raw_name in entry:
                name = raw_name.split("@", 1)[0]
                child_path = parent_path + "/" + name
                paths.add(child_path)
                # 网易UI运行时可把__default__模板层折叠为父控件直系路径，两种形式都视为有效。
                paths.add(child_path.replace("/__default__", ""))
                child = entry[raw_name]
                if "@" in raw_name:
                    inherited_roots.add(child_path)
                walk(child, child_path)

    main = data.get("main", {})
    walk(main, "")
    return paths, inherited_roots


def is_inherited_path(path, inherited_roots):
    if "/__default__" in path:
        return True
    return any(path == root or path.startswith(root + "/") for root in inherited_roots)


def validate_ui_paths():
    json_cache = {}
    for file_name in set(CLASS_UI_FILE.values()):
        path = resource_ui_root() / file_name
        data = json.loads(read_text(path))
        json_cache[file_name] = collect_control_paths(data)

    resolved = []
    inherited = []
    unresolved = []
    skipped = []
    for record in extract_config_paths():
        file_name = CLASS_UI_FILE.get(record["class"])
        if not file_name:
            skipped.append(record)
            continue
        paths, inherited_roots = json_cache[file_name]
        result = dict(record)
        result["json"] = "src/SwordSoul_NewERA_R/ui/" + file_name
        if record["path"] in paths:
            resolved.append(result)
        elif is_inherited_path(record["path"], inherited_roots):
            inherited.append(result)
        else:
            unresolved.append(result)
    return {
        "resolved_count": len(resolved),
        "inherited_or_runtime_count": len(inherited),
        "unresolved_count": len(unresolved),
        "unresolved": unresolved,
        "inherited_or_runtime": inherited,
        "skipped_without_json_mapping": skipped,
    }


def main():
    json_print(validate_ui_paths())


if __name__ == "__main__":
    main()
