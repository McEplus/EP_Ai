from __future__ import print_function

import argparse

from _common import json_print, project_root, read_text, relative


def main():
    parser = argparse.ArgumentParser(description="Trace a UI control path or UIConfig constant")
    parser.add_argument("query", help="Control path fragment, constant name, or JSON control name")
    args = parser.parse_args()
    roots = [
        project_root() / "src" / "SwordSoul_NewERA_B" / "SwordSoulFightScripts" / "UISystem",
        project_root() / "src" / "SwordSoul_NewERA_B" / "SwordSoulFightScripts" / "QingYunModLibs",
        project_root() / "src" / "SwordSoul_NewERA_R" / "ui",
    ]
    hits = []
    needle = args.query.lower()
    for root in roots:
        for path in root.rglob("*"):
            if path.suffix.lower() not in (".py", ".json"):
                continue
            for number, line in enumerate(read_text(path).splitlines(), 1):
                if needle in line.lower():
                    hits.append({"file": relative(path), "line": number, "text": line.strip()})
    json_print({"query": args.query, "occurrences": hits})


if __name__ == "__main__":
    main()
