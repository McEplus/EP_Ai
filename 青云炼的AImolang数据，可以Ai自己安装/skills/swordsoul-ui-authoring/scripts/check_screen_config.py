from __future__ import print_function

import argparse
import re
from pathlib import Path

from _common import behavior_ui_root, json_print, project_root, read_text, relative


ID_PATTERN = re.compile(r'["\']id["\']\s*:\s*["\']([^"\']+)["\']')
TYPE_PATTERN = re.compile(r'["\']touch_type["\']\s*:\s*["\']([^"\']+)["\']')
REGISTER_PATTERN = re.compile(r'RegisterRenderer\(\s*["\']([^"\']+)["\']')
DEFAULT_TYPES = {"Button", "Toggle", "Slider", "Label"}


def files_from_arg(value):
    if value:
        path = Path(value)
        if not path.is_absolute():
            path = project_root() / path
        return [path]
    return sorted(behavior_ui_root().glob("*.py"))


def check_file(path):
    text = read_text(path)
    ids = ID_PATTERN.findall(text)
    types = TYPE_PATTERN.findall(text)
    registered = DEFAULT_TYPES | set(REGISTER_PATTERN.findall(text))
    duplicates = sorted({item for item in ids if ids.count(item) > 1})
    unknown_types = sorted(set(types) - registered)
    return {
        "file": relative(path),
        "config_ids": len(ids),
        "touch_types": sorted(set(types)),
        "duplicate_ids_in_file": duplicates,
        "unregistered_types_in_file": unknown_types,
    }


def main():
    parser = argparse.ArgumentParser(description="Check static ScreenRenderConfig declarations")
    parser.add_argument("file", nargs="?", default="")
    args = parser.parse_args()
    results = [check_file(path) for path in files_from_arg(args.file)]
    json_print({"files": results})


if __name__ == "__main__":
    main()

