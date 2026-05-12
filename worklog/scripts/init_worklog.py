#!/usr/bin/env python3
from __future__ import annotations

import argparse

from worklog_lib import GLOBAL_ROOT, ensure_root, root_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Initialize project-local .worklog structure")
    parser.add_argument("--root", help=f"worklog root directory; defaults to the current project .worklog; use {GLOBAL_ROOT} for a global store")
    args = parser.parse_args()

    root = root_path(args.root)
    ensure_root(root)
    print(root)


if __name__ == "__main__":
    main()
