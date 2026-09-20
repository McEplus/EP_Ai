from __future__ import print_function

import argparse
import re

from _common import behavior_ui_root, json_print, read_text, relative, resource_ui_root


CLASS_PATTERN = re.compile(r"^class\s+(\w+)(?:\(([^)]*)\))?:", re.MULTILINE)


def build_inventory(name_filter=""):
    result = {"python": [], "json": []}
    python_roots = [
        behavior_ui_root(),
        behavior_ui_root().parent / "QingYunModLibs" / "ConfigUI"
    ]
    python_files = sorted(set(path for root in python_roots for path in root.rglob("*.py")))
    for path in python_files:
        if name_filter and name_filter.lower() not in path.name.lower():
            text = read_text(path)
            if name_filter.lower() not in text.lower():
                continue
        else:
            text = read_text(path)
        classes = [
            {"name": match.group(1), "bases": (match.group(2) or "").strip()}
            for match in CLASS_PATTERN.finditer(text)
        ]
        result["python"].append({
            "file": relative(path),
            "layer": "qingyun_config_ui" if "QingYunModLibs/ConfigUI" in relative(path) else "sws_ui",
            "lines": len(text.splitlines()),
            "classes": classes,
            "create_ui": sorted(set(re.findall(r'CreateUI\(["\']([^"\']+)', text))),
            "push_ui": sorted(set(re.findall(r'PushUI\(["\']([^"\']+)', text))),
            "config_items": len(re.findall(r'["\']touch_type["\']\s*:', text)),
        })
    for path in sorted(resource_ui_root().glob("*.json")):
        if name_filter and name_filter.lower() not in path.name.lower():
            continue
        text = read_text(path)
        result["json"].append({
            "file": relative(path),
            "lines": len(text.splitlines()),
        })
    return result


def main():
    parser = argparse.ArgumentParser(description="Inventory SWS UI Python and JSON assets")
    parser.add_argument("--screen", default="", help="Filter by screen or text name")
    args = parser.parse_args()
    json_print(build_inventory(args.screen))


if __name__ == "__main__":
    main()
