from __future__ import print_function

import argparse
import re

from _common import behavior_ui_root, json_print, read_text, relative


def main():
    parser = argparse.ArgumentParser(description="Trace configuration-driven screen declarations")
    parser.add_argument("screen")
    args = parser.parse_args()
    hits = []
    pattern = re.compile(r"class\s+%s\b" % re.escape(args.screen))
    for path in behavior_ui_root().rglob("*.py"):
        text = read_text(path)
        if not pattern.search(text):
            continue
        hits.append({
            "file": relative(path),
            "base_screen_render": "BaseScreenRenderCls" in text,
            "base_config_screen": "BaseConfigScreen" in text,
            "config_items": len(re.findall(r'["\']touch_type["\']\s*:', text)),
            "templates": sorted(set(re.findall(r'["\']template["\']\s*:\s*["\']([^"\']+)', text))),
        })
    json_print({"screen": args.screen, "matches": hits})


if __name__ == "__main__":
    main()

