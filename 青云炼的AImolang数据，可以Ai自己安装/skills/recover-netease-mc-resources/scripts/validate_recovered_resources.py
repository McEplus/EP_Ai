#!/usr/bin/env python3
"""Read-only JSON and identifier audit for recovered Bedrock resources."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


DEFINITION_ROOTS = {
    "animations": "animation",
    "animation_controllers": "animation_controller",
    "render_controllers": "render_controller",
    "particle_effect": "particle_effect",
}


def classify_document(document: dict[str, Any]) -> tuple[str, int, list[str]]:
    for root_key, resource_type in DEFINITION_ROOTS.items():
        definitions = document.get(root_key)
        if isinstance(definitions, dict):
            return resource_type, len(definitions), list(definitions)
    for root_key, resource_type in (
        ("minecraft:client_entity", "client_entity"),
        ("minecraft:attachable", "attachable"),
        ("minecraft:geometry", "geometry"),
    ):
        if root_key in document:
            value = document[root_key]
            count = len(value) if isinstance(value, list) else 1
            return resource_type, count, []
    return "other_json", 0, []


def looks_encrypted(path: Path) -> bool:
    try:
        with path.open("rb") as handle:
            prefix = handle.read(64)
        prefix[4:40].decode("ascii")
    except (OSError, UnicodeDecodeError):
        return False
    if len(prefix) < 64:
        return False
    text = prefix[4:40].decode("ascii")
    parts = text.split("-")
    return [len(part) for part in parts] == [8, 4, 4, 4, 12]


def audit(root: Path, include_files: bool) -> dict[str, Any]:
    type_counts = Counter()
    definition_counts = Counter()
    identifiers: dict[str, list[str]] = defaultdict(list)
    parse_errors: list[dict[str, str]] = []
    encrypted_files: list[str] = []
    file_rows: list[dict[str, Any]] = []
    json_files = sorted(root.rglob("*.json"), key=lambda item: str(item).lower())

    for path in json_files:
        if path.is_symlink():
            continue
        relative = path.relative_to(root).as_posix()
        if looks_encrypted(path):
            encrypted_files.append(relative)
            continue
        try:
            with path.open("r", encoding="utf-8-sig") as handle:
                document = json.load(handle)
            if not isinstance(document, dict):
                raise ValueError("JSON root is not an object")
        except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
            parse_errors.append({"path": relative, "error": str(exc)})
            continue

        resource_type, definition_count, names = classify_document(document)
        type_counts[resource_type] += 1
        definition_counts[resource_type] += definition_count
        for name in names:
            identifiers[name].append(relative)
        if include_files:
            file_rows.append(
                {
                    "path": relative,
                    "resource_type": resource_type,
                    "format_version": document.get("format_version"),
                    "definition_count": definition_count,
                }
            )

    duplicates = {
        name: paths for name, paths in sorted(identifiers.items()) if len(paths) > 1
    }
    report: dict[str, Any] = {
        "root": str(root.resolve()),
        "json_file_count": len(json_files),
        "parsed_json_count": sum(type_counts.values()),
        "resource_file_counts": dict(sorted(type_counts.items())),
        "definition_counts": dict(sorted(definition_counts.items())),
        "unique_definition_identifiers": len(identifiers),
        "duplicate_identifiers": duplicates,
        "encrypted_json_files": encrypted_files,
        "parse_errors": parse_errors,
    }
    if include_files:
        report["files"] = file_rows
    return report


def check_expectations(report: dict[str, Any], args: argparse.Namespace) -> list[str]:
    failures: list[str] = []
    counts = report["resource_file_counts"]
    if args.expected_animation_files is not None:
        actual = counts.get("animation", 0)
        if actual != args.expected_animation_files:
            failures.append(
                f"animation files: expected {args.expected_animation_files}, got {actual}"
            )
    if args.expected_controller_files is not None:
        actual = counts.get("animation_controller", 0)
        if actual != args.expected_controller_files:
            failures.append(
                f"controller files: expected {args.expected_controller_files}, got {actual}"
            )
    if args.strict:
        if report["parse_errors"]:
            failures.append(f"parse errors: {len(report['parse_errors'])}")
        if report["encrypted_json_files"]:
            failures.append(f"encrypted JSON files: {len(report['encrypted_json_files'])}")
        if report["duplicate_identifiers"]:
            failures.append(
                f"duplicate identifiers: {len(report['duplicate_identifiers'])}"
            )
        if report["parsed_json_count"] == 0:
            failures.append("no parsed JSON resources")
    return failures


def print_text(report: dict[str, Any], failures: list[str]) -> None:
    print(f"ROOT={report['root']}")
    print(f"JSON_FILES={report['json_file_count']}")
    print(f"PARSED={report['parsed_json_count']}")
    print("RESOURCE_FILES=" + json.dumps(report["resource_file_counts"], sort_keys=True))
    print("DEFINITIONS=" + json.dumps(report["definition_counts"], sort_keys=True))
    print(f"UNIQUE_IDENTIFIERS={report['unique_definition_identifiers']}")
    print(f"DUPLICATE_IDENTIFIERS={len(report['duplicate_identifiers'])}")
    print(f"ENCRYPTED_JSON={len(report['encrypted_json_files'])}")
    print(f"PARSE_ERRORS={len(report['parse_errors'])}")
    for row in report.get("files", []):
        print(
            "FILE "
            f"type={row['resource_type']} definitions={row['definition_count']} "
            f"format={row['format_version']} path={row['path']}"
        )
    for failure in failures:
        print(f"FAIL={failure}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path, help="Recovered resource root")
    parser.add_argument("--strict", action="store_true", help="Fail on parse, encryption, or duplicates")
    parser.add_argument("--json", action="store_true", help="Print JSON report")
    parser.add_argument("--include-files", action="store_true", help="Include per-file results")
    parser.add_argument("--expected-animation-files", type=int)
    parser.add_argument("--expected-controller-files", type=int)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.root.is_dir():
        print(f"ERROR: not a directory: {args.root}", file=sys.stderr)
        return 2
    report = audit(args.root, args.include_files)
    failures = check_expectations(report, args)
    if args.json:
        report["validation_failures"] = failures
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print_text(report, failures)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
