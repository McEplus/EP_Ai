from __future__ import print_function

import json
import re

from _common import behavior_ui_root, json_print, read_text, relative, resource_ui_root


SEMANTIC_CHILDREN = {"TouchButton", "TouchToggle", "TouchSlider", "Label", "Value", "Icon", "NameLabel"}


def collect_candidates(node, path, output):
    if not isinstance(node, dict):
        return
    controls = node.get("controls", [])
    if not isinstance(controls, list):
        return
    child_names = []
    children = []
    for entry in controls:
        if not isinstance(entry, dict):
            continue
        for raw_name in entry:
            name = raw_name.split("@", 1)[0]
            child_names.append(name)
            children.append((name, entry[raw_name]))
    matched = sorted(set(child_names) & SEMANTIC_CHILDREN)
    if len(matched) >= 2 or any(name in child_names for name in ("TouchToggle", "TouchSlider")):
        output.append({"path": path or "/", "semantic_children": matched})
    for name, child in children:
        collect_candidates(child, path + "/" + name, output)


def main():
    templates = []
    for path in sorted(resource_ui_root().glob("*.json")):
        if path.name == "_ui_defs.json":
            continue
        data = json.loads(read_text(path))
        candidates = []
        collect_candidates(data.get("main", {}), "", candidates)
        if candidates:
            templates.append({"file": relative(path), "candidates": candidates})
    registrations = []
    roots = [behavior_ui_root(), behavior_ui_root().parent / "QingYunModLibs" / "ConfigUI"]
    for root in roots:
        for path in root.rglob("*.py"):
            text = read_text(path)
            names = re.findall(r'RegisterTemplate\(\s*["\']([^"\']+)', text)
            if names:
                registrations.append({"file": relative(path), "templates": sorted(set(names))})
    json_print({"json_template_candidates": templates, "python_registrations": registrations})


if __name__ == "__main__":
    main()

