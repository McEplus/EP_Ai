from __future__ import print_function

import argparse
import sys

from _common import json_print
from audit_input_bindings import audit_input_bindings
from check_screen_config import check_file, files_from_arg
from validate_ui_json import validate_ui_json
from validate_ui_paths import validate_ui_paths


def build_audit():
    json_result = validate_ui_json()
    path_result = validate_ui_paths()
    input_result = audit_input_bindings()
    config_results = [check_file(path) for path in files_from_arg("")]
    blocking = []
    if json_result["parse_errors"]:
        blocking.append("UI JSON parse errors")
    if json_result["missing_declared_files"]:
        blocking.append("_ui_defs.json references missing files")
    if json_result["unresolved_namespaces"]:
        blocking.append("UI inheritance namespaces are unresolved")
    if input_result["findings"]:
        blocking.append("stateful UI buttons have incomplete release bindings")
    if any(item["unregistered_types_in_file"] for item in config_results):
        blocking.append("ScreenRenderConfig contains unregistered touch types")
    return {
        "status": "pass" if not blocking else "findings",
        "blocking_findings": blocking,
        "json": json_result,
        "paths": path_result,
        "inputs": input_result,
        "screen_configs": config_results,
        "notes": [
            "Unresolved UIConfig paths are advisory because inherited and runtime-cloned controls may not exist literally in JSON.",
            "Texture references absent from the project pack are advisory because NetEase/Bedrock may provide built-in UI textures.",
            "Static audit does not replace in-game render, input, persistence, and unRender verification."
        ]
    }


def main():
    parser = argparse.ArgumentParser(description="Run the complete offline SwordSoul UI audit")
    parser.add_argument("--strict", action="store_true", help="Exit non-zero when blocking findings exist")
    args = parser.parse_args()
    result = build_audit()
    json_print(result)
    if args.strict and result["blocking_findings"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
