from __future__ import print_function

import argparse

from _common import json_print, setting_occurrences


def classify(item, setting_id):
    text = item["text"]
    if "self.%s" % setting_id in text:
        return "default_or_runtime_field"
    if "SetLocalConfig" in text:
        return "persistence_registration"
    if '"id"' in text or "'id'" in text:
        return "screen_config"
    if "def on%s" % setting_id in text:
        return "apply_callback"
    if "getChoose" in text or "updateChoose" in text:
        return "state_access"
    return "consumer_or_reference"


def main():
    parser = argparse.ArgumentParser(description="Trace one SWS setting through UI and runtime code")
    parser.add_argument("setting_id")
    args = parser.parse_args()
    occurrences = setting_occurrences(args.setting_id)
    for item in occurrences:
        item["kind"] = classify(item, args.setting_id)
    kinds = set(item["kind"] for item in occurrences)
    json_print({
        "setting": args.setting_id,
        "coverage": {
            "default_field": "default_or_runtime_field" in kinds,
            "persistence_registration": "persistence_registration" in kinds,
            "screen_config": "screen_config" in kinds,
            "apply_callback": "apply_callback" in kinds,
            "consumer_or_reference": "consumer_or_reference" in kinds,
        },
        "occurrences": occurrences,
    })


if __name__ == "__main__":
    main()
