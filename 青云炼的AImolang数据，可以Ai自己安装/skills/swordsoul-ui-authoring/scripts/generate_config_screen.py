from __future__ import print_function

import argparse
import sys
from pathlib import Path


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Print a ConfigUI screen draft without writing game files")
    parser.add_argument("class_name")
    parser.add_argument("--kind", choices=("generic", "sws-setting"), default="generic")
    parser.add_argument("--columns", type=int, default=1)
    parser.add_argument("--ui-name", default='"ExampleUI"')
    parser.add_argument("--scroll-path", default='"/Control/ScrollView"')
    parser.add_argument("--screen-path", default='"/Control/ScrollView/Content"')
    parser.add_argument("--block-path", default='"/Control/ScrollView/Content/BaseComp"')
    args = parser.parse_args()
    if args.kind == "sws-setting":
        base_import = "SwordSoulFightScripts.UISystem.ConfigUI.SettingScreen"
        base_class = "BaseSWSSettingScreen"
    else:
        base_import = "SwordSoulFightScripts.QingYunModLibs.ConfigUI.ConfigScreen"
        base_class = "BaseConfigScreen"
    template_path = Path(__file__).resolve().parents[1] / "assets" / "templates" / "config-screen.py.tpl"
    template = template_path.read_text(encoding="utf-8")
    print(template.format(
        base_import=base_import,
        base_class=base_class,
        class_name=args.class_name,
        columns=max(1, args.columns),
        ui_name=args.ui_name,
        scroll_path=args.scroll_path,
        screen_path=args.screen_path,
        block_path=args.block_path,
    ))


if __name__ == "__main__":
    main()
