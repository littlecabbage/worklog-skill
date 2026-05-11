#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from worklog_lib import DEFAULT_ROOT, ensure_root, write_json


def main() -> None:
    parser = argparse.ArgumentParser(description="Initialize ~/.claude/worklog structure")
    parser.add_argument("--root", default=str(DEFAULT_ROOT), help="worklog root directory")
    args = parser.parse_args()

    root = Path(args.root).expanduser()
    ensure_root(root)
    print(root)


if __name__ == "__main__":
    main()
