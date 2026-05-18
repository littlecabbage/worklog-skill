#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys

from worklog_lib import (
    build_worklog_entry,
    build_worklog_frontmatter,
    choose_worklog_file,
    GLOBAL_ROOT,
    date_only,
    ensure_relative,
    ensure_root,
    is_body_payload,
    load_input,
    load_index_json,
    next_id,
    normalize_experience,
    parse_experience_entries,
    project_slug,
    rebuild_indexes,
    render_frontmatter,
    root_path,
    validate_body_payload,
)


def emit_warnings(warnings: list[str]) -> None:
    for line in warnings:
        sys.stderr.write(f"warning: {line}\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Append a worklog and update indexes")
    parser.add_argument("--root", help=f"worklog root directory; defaults to the current project .worklog; use {GLOBAL_ROOT} for a global store")
    parser.add_argument("--input", help="path to input JSON; otherwise read stdin")
    parser.add_argument("--validate-only", action="store_true", help="validate payload and exit without writing")
    args = parser.parse_args()

    payload = load_input(args.input)

    if not is_body_payload(payload):
        if "sections" in payload:
            raise SystemExit(
                "the legacy `sections` payload is no longer supported; pass a `body` markdown string instead. "
                "See references/worklog-format.zh.md."
            )
        raise SystemExit("payload must include a `body` field (markdown string).")

    warnings = validate_body_payload(payload)
    emit_warnings(warnings)
    body = payload["body"].rstrip() + "\n"

    if args.validate_only:
        print("ok")
        return

    root = root_path(args.root, payload["project_path"])
    ensure_root(root)
    index = load_index_json(root)

    mode = payload["mode"]
    project = project_slug(payload["project_path"], payload.get("project"))
    day = date_only(payload["started_at"])
    if mode == "debug-session" and payload.get("debug_id") and not payload.get("session_number"):
        existing = [item for item in index.get("worklogs", []) if item.get("debug_id") == payload["debug_id"]]
        payload["session_number"] = len(existing) + 1

    worklog_id = next_id("wl", day, [item["id"] for item in index.get("worklogs", [])])
    payload.setdefault("produced_experience_ids", [])
    frontmatter = build_worklog_frontmatter(payload, worklog_id, project)

    directory = root / project / day if args.root else root / day
    directory.mkdir(parents=True, exist_ok=True)
    output_path = choose_worklog_file(directory, payload["title"])
    output_path.write_text(render_frontmatter(frontmatter) + "\n\n" + body + "\n", encoding="utf-8")
    relative_path = ensure_relative(output_path, root)

    worklog_entry = build_worklog_entry(frontmatter, relative_path)
    worklogs = [item for item in index.get("worklogs", []) if item["id"] != worklog_id]
    worklogs.append(worklog_entry)

    existing_entries = parse_experience_entries(root)
    existing_ids = [entry["id"] for entry in existing_entries]
    new_entries = []
    for exp in payload.get("experiences", []):
        exp_id = next_id("exp", day, existing_ids + [entry["id"] for entry in new_entries])
        new_entry = normalize_experience(exp, worklog_id, project, relative_path, day, exp_id)
        new_entries.append(new_entry)
        payload["produced_experience_ids"].append(exp_id)

    frontmatter["produced_experience_ids"] = payload["produced_experience_ids"]
    output_path.write_text(render_frontmatter(frontmatter) + "\n\n" + body + "\n", encoding="utf-8")

    rebuild_indexes(root, existing_entries + new_entries)

    print(output_path)


if __name__ == "__main__":
    main()
