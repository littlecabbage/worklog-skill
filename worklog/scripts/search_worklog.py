#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from worklog_lib import DEFAULT_ROOT, load_index_json


def matches_text(item: dict, query: str) -> bool:
    haystacks = [
        item.get("title", ""),
        item.get("summary", ""),
        " ".join(item.get("tags", [])),
        " ".join(item.get("search_keywords", [])),
        item.get("project", ""),
    ]
    target = query.lower()
    return any(target in value.lower() for value in haystacks if isinstance(value, str))


def main() -> None:
    parser = argparse.ArgumentParser(description="Search worklog experiences and sessions")
    parser.add_argument("query", nargs="?", default="")
    parser.add_argument("--root", default=str(DEFAULT_ROOT), help="worklog root directory")
    parser.add_argument("--tag")
    parser.add_argument("--project")
    parser.add_argument("--type", choices=["experiences", "worklogs"], default="experiences")
    args = parser.parse_args()

    root = Path(args.root).expanduser()
    index = load_index_json(root)
    items = index[args.type]

    filtered = []
    for item in items:
        if args.tag and args.tag not in item.get("tags", []):
            continue
        if args.project and args.project != item.get("project"):
            continue
        if args.query and not matches_text(item, args.query):
            continue
        filtered.append(item)

    print(json.dumps(filtered, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
