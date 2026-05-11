#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from worklog_lib import DEFAULT_ROOT, reindex


def main() -> None:
    parser = argparse.ArgumentParser(description="Rebuild INDEX.md and index.json from markdown")
    parser.add_argument("--root", default=str(DEFAULT_ROOT), help="worklog root directory")
    args = parser.parse_args()

    root = Path(args.root).expanduser()
    index = reindex(root)
    print(f"worklogs={len(index['worklogs'])} experiences={len(index['experiences'])}")


if __name__ == "__main__":
    main()
