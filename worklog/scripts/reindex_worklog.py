#!/usr/bin/env python3
from __future__ import annotations

import argparse

from worklog_lib import GLOBAL_ROOT, reindex, root_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Rebuild INDEX.md and index.json from markdown")
    parser.add_argument("--root", help=f"worklog root directory; defaults to the current project .worklog; use {GLOBAL_ROOT} for a global store")
    args = parser.parse_args()

    root = root_path(args.root)
    index = reindex(root)
    print(f"worklogs={len(index['worklogs'])} experiences={len(index['experiences'])}")


if __name__ == "__main__":
    main()
