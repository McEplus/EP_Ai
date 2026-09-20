#!/usr/bin/env python3
"""剑魂学习手册三章完整性交付检查。"""

from __future__ import print_function

import ast
import re
import runpy
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
CATALOG_PATH = ROOT / "src/SwordSoul_NewERA_B/SwordSoulFightScripts/UISystem/TutorialCatalog.py"
PRACTICE_PATH = ROOT / "src/SwordSoul_NewERA_B/SwordSoulFightScripts/UISystem/TutorialPractice.py"
RESOURCE = ROOT / "src/SwordSoul_NewERA_R"


def load_catalog():
    return runpy.run_path(str(CATALOG_PATH))["TUTORIAL_CATALOG"]


def assert_texture(texture):
    assert any((RESOURCE / (texture + extension)).is_file() for extension in (".png", ".tga")), texture


def visible_strings(value):
    keys = {
        "title", "summary", "caption", "details", "input_hint", "instruction",
        "hint", "success", "retry", "label", "watch", "prompt",
    }
    if isinstance(value, dict):
        for key, child in value.items():
            if key in keys and isinstance(child, str):
                yield child
            for text in visible_strings(child):
                yield text
    elif isinstance(value, list):
        for child in value:
            for text in visible_strings(child):
                yield text


def main():
    catalog = load_catalog()
    assert [chapter["id"] for chapter in catalog] == ["basic_ui", "moves", "mechanics"]
    expected_pages = {"basic_ui": 10, "moves": 14, "mechanics": 10}
    total_pages = 0
    total_steps = 0
    page_ids = set()
    for chapter in catalog:
        pages = [page for section in chapter["sections"] for page in section["pages"]]
        assert len(pages) == expected_pages[chapter["id"]]
        for page in pages:
            page_id = page.get("id")
            assert page_id and page_id not in page_ids
            page_ids.add(page_id)
            assert page.get("track", True) is True, page_id
            assert page.get("title") and page.get("summary") and page.get("details") and page.get("input_hint"), page_id
            assert page.get("illustration", {}).get("texture") and page["illustration"].get("caption"), page_id
            assert_texture(page["illustration"]["texture"])
            practice = page.get("practice", {})
            assert practice.get("steps"), page_id
            for step in practice["steps"]:
                for key in ("title", "instruction", "hint", "action", "success", "retry", "icon"):
                    assert step.get(key), (page_id, key)
                assert_texture(step["icon"])
                assert len(step.get("stages", [])) <= 4, (page_id, step["title"])
                total_steps += 1
            total_pages += 1
    assert total_pages == 34
    assert total_steps == 66

    basic = next(chapter for chapter in catalog if chapter["id"] == "basic_ui")
    basic_pages = {
        page["id"]: page
        for section in basic["sections"]
        for page in section["pages"]
    }
    attack_steps = basic_pages["attack"]["practice"]["steps"]
    dodge_steps = basic_pages["dodge"]["practice"]["steps"]
    assert len(attack_steps) == 1 and attack_steps[0]["action"] == "attack_up"
    assert [stage["action"] for stage in attack_steps[0]["stages"]] == ["attack_down", "attack_up"]
    assert [step["action"] for step in dodge_steps] == ["dodge_up", "dodge_up"]
    assert all([stage["action"] for stage in step["stages"]] == ["dodge_down", "dodge_up"] for step in dodge_steps)
    assert "向左" in dodge_steps[0]["title"] and "向右" in dodge_steps[1]["title"]
    assert all(step["require_stage_completion"] for step in attack_steps + dodge_steps)

    source = CATALOG_PATH.read_text(encoding="utf-8-sig")
    for unfinished in ("内容制作中", "_planned", '"track": False', "第二阶段加入"):
        assert unfinished not in source, unfinished
    for text in visible_strings(catalog):
        assert not re.search(r"[A-Za-z_]", text), "player-facing English/technical text: %r" % text
        assert not any(word in text for word in ("服务器", "客户端", "开发者", "状态编号")), text

    practice_source = PRACTICE_PATH.read_text(encoding="utf-8-sig")
    assert 'ProgressSystem.MarkPracticed(self.ActivePageId)' in practice_source
    assert 'CreateTimer(0.12, self._returnToBook, False, ReturnToken)' in practice_source
    assert 'PushUI("UISystem.TutorialScreen")' in practice_source
    print("complete tutorial handbook regression: PASS (%d pages, %d practical steps)" % (total_pages, total_steps))


if __name__ == "__main__":
    main()
