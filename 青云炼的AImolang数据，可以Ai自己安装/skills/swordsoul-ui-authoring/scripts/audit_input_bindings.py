from __future__ import print_function

import re

from _common import behavior_ui_root, json_print, read_text, relative


BUTTON_PATTERN = re.compile(
    r'@AddButton\(ControlConfig\.([A-Za-z0-9_]+),\s*"(Down|Up|Cancel|Move)"'
)
INTENTIONAL_DOWN_ONLY = {"CancelTouch": "全屏触摸吞噬层只处理按下事件"}


def audit_input_bindings():
    path = behavior_ui_root() / "Control.py"
    text = read_text(path)
    controls = {}
    for control, state in BUTTON_PATTERN.findall(text):
        controls.setdefault(control, set()).add(state)
    findings = []
    exceptions = []
    for control in sorted(controls):
        states = controls[control]
        if "Down" in states and "Up" not in states and "Cancel" not in states:
            if control in INTENTIONAL_DOWN_ONLY:
                exceptions.append({"control": control, "reason": INTENTIONAL_DOWN_ONLY[control]})
            else:
                findings.append({"control": control, "finding": "Down has no Up or Cancel decorator"})
    return {
        "file": relative(path),
        "controls": {key: sorted(value) for key, value in controls.items()},
        "findings": findings,
        "intentional_exceptions": exceptions,
    }


def main():
    json_print(audit_input_bindings())


if __name__ == "__main__":
    main()
