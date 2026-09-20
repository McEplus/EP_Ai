from __future__ import print_function

import argparse
import re

from _common import behavior_ui_root, json_print, read_text, relative


def trace_input(query):
    path = behavior_ui_root() / "Control.py"
    lines = read_text(path).splitlines()
    lowered = query.lower()
    matches = []
    for index, line in enumerate(lines):
        if lowered not in line.lower():
            continue
        start = max(0, index - 4)
        end = min(len(lines), index + 7)
        matches.append({
            "file": relative(path),
            "line": index + 1,
            "context": [item.rstrip() for item in lines[start:end]],
        })
    consumers = []
    fight_root = behavior_ui_root().parent / "FightSystem"
    for source in fight_root.glob("*.py"):
        for number, line in enumerate(read_text(source).splitlines(), 1):
            if lowered in line.lower():
                consumers.append({"file": relative(source), "line": number, "text": line.strip()})
    return {"query": query, "bindings": matches, "fight_consumers": consumers}


def main():
    parser = argparse.ArgumentParser(description="Trace one SWS HUD/input action")
    parser.add_argument("query")
    args = parser.parse_args()
    json_print(trace_input(args.query))


if __name__ == "__main__":
    main()

