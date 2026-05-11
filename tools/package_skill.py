#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
import zipfile
from pathlib import Path


def validate_skill(skill_dir: Path) -> None:
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists():
        raise SystemExit("missing SKILL.md")
    text = skill_md.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise SystemExit("SKILL.md must start with YAML frontmatter")
    required = ["name:", "description:"]
    for item in required:
        if item not in text.split("---", 2)[1]:
            raise SystemExit(f"SKILL.md frontmatter missing {item}")


def package_skill(skill_dir: Path, output_dir: Path) -> Path:
    validate_skill(skill_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    archive_path = output_dir / f"{skill_dir.name}.skill"
    if archive_path.exists():
        archive_path.unlink()
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(skill_dir.rglob("*")):
            if not path.is_file():
                continue
            if "__pycache__" in path.parts:
                continue
            zf.write(path, arcname=str(Path(skill_dir.name) / path.relative_to(skill_dir)))
    return archive_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate and package a Claude skill")
    parser.add_argument("skill_dir")
    parser.add_argument("output_dir", nargs="?", default="dist")
    args = parser.parse_args()

    skill_dir = Path(args.skill_dir).resolve()
    output_dir = Path(args.output_dir).resolve()
    artifact = package_skill(skill_dir, output_dir)
    print(artifact)


if __name__ == "__main__":
    main()
