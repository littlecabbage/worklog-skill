#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from worklog_lib import (
    DEFAULT_ROOT,
    build_worklog_entry,
    build_worklog_frontmatter,
    choose_worklog_file,
    date_only,
    ensure_relative,
    ensure_root,
    load_index_json,
    load_input,
    next_id,
    normalize_experience,
    parse_experience_entries,
    project_slug,
    refresh_debug_sessions,
    render_experiences_md,
    render_frontmatter,
    render_index_md,
    render_worklog_body,
    validate_payload,
    write_index_json,
    compute_stats,
    build_experience_record,
    find_anchor_line,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Append a worklog and update indexes")
    parser.add_argument("--root", default=str(DEFAULT_ROOT), help="worklog root directory")
    parser.add_argument("--input", help="path to input JSON; otherwise read stdin")
    args = parser.parse_args()

    payload = load_input(args.input)
    validate_payload(payload)

    root = Path(args.root).expanduser()
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
    body = render_worklog_body(payload)

    directory = root / project / day
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

    all_entries = existing_entries + new_entries
    experiences_md = render_experiences_md(all_entries)
    (root / "EXPERIENCES.md").write_text(experiences_md, encoding="utf-8")

    source_map = {item["id"]: item for item in worklogs}
    experiences = []
    for entry in all_entries:
        line = find_anchor_line(experiences_md, entry["id"])
        experiences.append(build_experience_record(entry, source_map, line))

    final_index = {
        "version": 1,
        "updated_at": index.get("updated_at"),
        "experiences": sorted(experiences, key=lambda item: (item["date"], item["id"]), reverse=True),
        "worklogs": sorted(worklogs, key=lambda item: (item["date"], item["id"]), reverse=True),
        "snippets": payload.get("snippets", index.get("snippets", [])),
        "debug_sessions": refresh_debug_sessions(worklogs),
        "stats": compute_stats(worklogs, experiences),
    }
    write_index_json(root, final_index)
    (root / "INDEX.md").write_text(render_index_md(worklogs), encoding="utf-8")

    print(output_path)


if __name__ == "__main__":
    main()
