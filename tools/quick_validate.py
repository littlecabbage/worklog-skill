#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate minimal Claude skill structure")
    parser.add_argument("skill_dir")
    args = parser.parse_args()

    skill_dir = Path(args.skill_dir).resolve()
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists():
        raise SystemExit("missing SKILL.md")
    text = skill_md.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise SystemExit("SKILL.md must start with YAML frontmatter")
    frontmatter = text.split("---", 2)[1]
    if "name:" not in frontmatter or "description:" not in frontmatter:
        raise SystemExit("SKILL.md frontmatter must contain name and description")
    print("Skill is valid!")


if __name__ == "__main__":
    main()
