from __future__ import print_function

import argparse

from _common import json_print, project_root, read_text, relative, setting_occurrences
from trace_input import trace_input
from ui_inventory import build_inventory


def query_path(value):
    roots = [
        project_root() / "src" / "SwordSoul_NewERA_B" / "SwordSoulFightScripts" / "UISystem",
        project_root() / "src" / "SwordSoul_NewERA_B" / "SwordSoulFightScripts" / "QingYunModLibs",
        project_root() / "src" / "SwordSoul_NewERA_R" / "ui",
    ]
    hits = []
    needle = value.lower()
    for root in roots:
        for path in root.rglob("*"):
            if path.suffix.lower() not in (".py", ".json"):
                continue
            for number, line in enumerate(read_text(path).splitlines(), 1):
                if needle in line.lower():
                    hits.append({"file": relative(path), "line": number, "text": line.strip()})
    return {"query": value, "occurrences": hits}


def main():
    parser = argparse.ArgumentParser(description="Unified SwordSoul UI query")
    parser.add_argument("kind", choices=("screen", "setting", "path", "input"))
    parser.add_argument("query")
    args = parser.parse_args()
    if args.kind == "screen":
        result = build_inventory(args.query)
    elif args.kind == "setting":
        result = {"setting": args.query, "occurrences": setting_occurrences(args.query)}
    elif args.kind == "input":
        result = trace_input(args.query)
    else:
        result = query_path(args.query)
    json_print(result)


if __name__ == "__main__":
    main()
