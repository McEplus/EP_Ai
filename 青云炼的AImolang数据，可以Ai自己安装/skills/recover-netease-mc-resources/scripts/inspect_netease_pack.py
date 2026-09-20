#!/usr/bin/env python3
"""Read-only inventory and encrypted-header classifier for a NetEase MC pack."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any


UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)


def classify_prefix(prefix: bytes, suffix: str) -> dict[str, Any]:
    result: dict[str, Any] = {"kind": "binary_or_unknown"}
    if len(prefix) >= 64:
        try:
            uuid_text = prefix[4:40].decode("ascii")
        except UnicodeDecodeError:
            uuid_text = ""
        if UUID_RE.fullmatch(uuid_text):
            result.update(
                {
                    "kind": "netease_uuid_header",
                    "uuid": uuid_text.lower(),
                    "marker_hex": prefix[:4].hex(),
                    "reserved_zero": all(byte == 0 for byte in prefix[40:64]),
                    "ciphertext_offset": 64,
                }
            )
            return result

    stripped = prefix.lstrip()
    if suffix.lower() == ".json" and stripped.startswith((b"{", b"[")):
        result["kind"] = "plaintext_json_candidate"
    elif stripped.startswith((b"{", b"[")):
        result["kind"] = "plaintext_structured_candidate"
    return result


def inventory(root: Path, include_files: bool) -> dict[str, Any]:
    counts = Counter()
    suffixes = Counter()
    top_dirs = Counter()
    uuids = Counter()
    errors: list[dict[str, str]] = []
    file_rows: list[dict[str, Any]] = []
    total_bytes = 0

    for path in sorted(root.rglob("*"), key=lambda item: str(item).lower()):
        if path.is_symlink() or not path.is_file():
            continue
        relative = path.relative_to(root)
        try:
            size = path.stat().st_size
            with path.open("rb") as handle:
                prefix = handle.read(4096)
        except OSError as exc:
            errors.append({"path": relative.as_posix(), "error": str(exc)})
            continue

        classified = classify_prefix(prefix, path.suffix)
        kind = classified["kind"]
        counts[kind] += 1
        suffixes[path.suffix.lower() or "<none>"] += 1
        top_dirs[relative.parts[0] if len(relative.parts) > 1 else "<root>"] += 1
        total_bytes += size
        if "uuid" in classified:
            uuids[classified["uuid"]] += 1
        if include_files:
            file_rows.append(
                {
                    "path": relative.as_posix(),
                    "size": size,
                    **classified,
                }
            )

    report: dict[str, Any] = {
        "root": str(root.resolve()),
        "file_count": sum(counts.values()),
        "total_bytes": total_bytes,
        "classification_counts": dict(sorted(counts.items())),
        "top_level_counts": dict(sorted(top_dirs.items())),
        "suffix_counts": dict(sorted(suffixes.items())),
        "wrapper_uuids": dict(sorted(uuids.items())),
        "read_errors": errors,
    }
    if include_files:
        report["files"] = file_rows
    return report


def print_text(report: dict[str, Any]) -> None:
    print(f"ROOT={report['root']}")
    print(f"FILES={report['file_count']}")
    print(f"BYTES={report['total_bytes']}")
    print("CLASSIFICATIONS=" + json.dumps(report["classification_counts"], sort_keys=True))
    print("TOP_LEVEL=" + json.dumps(report["top_level_counts"], sort_keys=True))
    print("SUFFIXES=" + json.dumps(report["suffix_counts"], sort_keys=True))
    print("WRAPPER_UUIDS=" + json.dumps(report["wrapper_uuids"], sort_keys=True))
    print(f"READ_ERRORS={len(report['read_errors'])}")
    for row in report.get("files", []):
        details = ""
        if row["kind"] == "netease_uuid_header":
            details = f" uuid={row['uuid']} marker={row['marker_hex']}"
        print(f"FILE kind={row['kind']} size={row['size']} path={row['path']}{details}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path, help="Installed resource- or behavior-pack root")
    parser.add_argument("--json", action="store_true", help="Print JSON report")
    parser.add_argument(
        "--include-files", action="store_true", help="Include every relative file in output"
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.root.is_dir():
        print(f"ERROR: not a directory: {args.root}", file=sys.stderr)
        return 2
    report = inventory(args.root, args.include_files)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print_text(report)
    return 1 if report["read_errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
