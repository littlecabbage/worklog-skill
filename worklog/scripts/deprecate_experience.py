#!/usr/bin/env python3
from __future__ import annotations

import argparse

from worklog_lib import GLOBAL_ROOT, get_experience_by_id, parse_experience_entries, rebuild_indexes, root_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Mark an experience as deprecated or wrong")
    parser.add_argument("experience_id")
    parser.add_argument("reason")
    parser.add_argument("--status", choices=["deprecated", "wrong"], default="deprecated")
    parser.add_argument("--root", help=f"worklog root directory; defaults to the current project .worklog; use {GLOBAL_ROOT} for a global store")
    args = parser.parse_args()

    root = root_path(args.root)
    entries = parse_experience_entries(root)
    entry = get_experience_by_id(entries, args.experience_id)
    entry["meta"]["status"] = args.status
    entry["meta"]["deprecated_reason"] = args.reason
    entry["meta"]["deprecated_at"] = entry["meta"].get("deprecated_at") or entry["date"]
    if not entry["title_line"].startswith("~~"):
        entry["title_line"] = f"~~{entry['title']}~~"
    if "**Reason**:" not in entry["body"] and "**原因**:" not in entry["body"]:
        entry["body"] = entry["body"].rstrip() + f"\n\n**Reason**: {args.reason}"

    rebuild_indexes(root, entries)
    print(args.experience_id)


if __name__ == "__main__":
    main()
