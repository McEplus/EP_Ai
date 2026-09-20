from __future__ import print_function

import json
import re
import subprocess
import sys
from pathlib import Path


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def project_root():
    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / ".codex").is_dir() and (parent / "src").is_dir():
            return parent
    raise RuntimeError("SwordSoul project root was not found")


def behavior_ui_root():
    return project_root() / "src" / "SwordSoul_NewERA_B" / "SwordSoulFightScripts" / "UISystem"


def resource_ui_root():
    return project_root() / "src" / "SwordSoul_NewERA_R" / "ui"


def read_text(path):
    return Path(path).read_text(encoding="utf-8")


def relative(path):
    return str(Path(path).resolve().relative_to(project_root())).replace("\\", "/")


def json_print(data):
    print(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True))


def setting_occurrences(setting_id):
    escaped = re.escape(setting_id)
    pattern = re.compile(r"(?:\b%s\b|\bon%s\b)" % (escaped, escaped))
    results = []
    roots = [
        project_root() / "src" / "SwordSoul_NewERA_B" / "SwordSoulFightScripts",
        project_root() / "src" / "SwordSoul_NewERA_R" / "ui",
    ]
    for root in roots:
        for path in root.rglob("*"):
            if path.suffix.lower() not in (".py", ".json"):
                continue
            text = read_text(path)
            for number, line in enumerate(text.splitlines(), 1):
                if pattern.search(line):
                    results.append({"file": relative(path), "line": number, "text": line.strip()})
    return results


def git_changed_files():
    process = subprocess.run(
        ["git", "diff", "--name-only", "--", ".", ":(exclude).build"],
        cwd=str(project_root()),
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    )
    untracked = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard"],
        cwd=str(project_root()),
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    )
    files = [line.strip() for line in process.stdout.splitlines() if line.strip()]
    files.extend(line.strip() for line in untracked.stdout.splitlines() if line.strip())
    return sorted(set(path.replace("\\", "/") for path in files if not path.startswith(".build/")))
