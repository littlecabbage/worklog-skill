#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

DEFAULT_ROOT = Path.home() / ".claude" / "worklog"
VALID_MODES = {"dev", "read", "debug-session", "mixed"}
WORKLOG_STATUSES = {"completed", "partial", "paused", "blocked", "abandoned"}
EXPERIENCE_STATUSES = {"active", "deprecated", "wrong", "evolving"}
CONFIDENCE_LEVELS = {"high", "medium", "low"}


def root_path(value: str | None = None) -> Path:
    return Path(value).expanduser() if value else DEFAULT_ROOT


def ensure_root(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "archive").mkdir(exist_ok=True)
    if not (root / "INDEX.md").exists():
        (root / "INDEX.md").write_text("# Work Log Index\n", encoding="utf-8")
    if not (root / "EXPERIENCES.md").exists():
        (root / "EXPERIENCES.md").write_text(
            "# Experience Library\n\n> Newest first. Keep original wording when deprecating. Mark stale or wrong content with `~~...~~` and add a reason.\n",
            encoding="utf-8",
        )
    if not (root / "index.json").exists():
        write_index_json(root, empty_index())


def empty_index() -> dict[str, Any]:
    return {
        "version": 1,
        "updated_at": iso_now(),
        "experiences": [],
        "worklogs": [],
        "snippets": [],
        "debug_sessions": [],
        "stats": {"by_tag": {}, "by_project": {}, "by_status": {}, "by_mode": {}},
    }


def iso_now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def parse_date(value: str) -> datetime:
    return datetime.fromisoformat(value)


def date_only(value: str) -> str:
    return parse_date(value).date().isoformat()


def slugify(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip().lower())
    cleaned = re.sub(r"-+", "-", cleaned).strip("-._")
    return cleaned or "untitled"


def project_slug(project_path: str, explicit: str | None = None) -> str:
    if explicit:
        return slugify(explicit)
    return slugify(Path(project_path).name or "project")


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_index_json(root: Path) -> dict[str, Any]:
    return read_json(root / "index.json", empty_index())


def write_index_json(root: Path, payload: dict[str, Any]) -> None:
    payload["updated_at"] = iso_now()
    write_json(root / "index.json", payload)


def load_input(path: str | None) -> dict[str, Any]:
    if path:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    raw = os.sys.stdin.read().strip()
    if not raw:
        raise SystemExit("missing input JSON")
    return json.loads(raw)


def next_id(prefix: str, day: str, existing_ids: list[str]) -> str:
    numbers = []
    needle = f"{prefix}-{day}-"
    for item in existing_ids:
        if item.startswith(needle):
            tail = item[len(needle):]
            if tail.isdigit():
                numbers.append(int(tail))
    return f"{prefix}-{day}-{max(numbers, default=0) + 1:03d}"


def choose_worklog_file(directory: Path, title: str) -> Path:
    slug = slugify(title)
    candidate = directory / f"{slug}.md"
    if not candidate.exists():
        return candidate
    i = 2
    while True:
        candidate = directory / f"{slug}-{i}.md"
        if not candidate.exists():
            return candidate
        i += 1


def jsonish(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def render_frontmatter(data: dict[str, Any]) -> str:
    lines = ["---"]
    for key, value in data.items():
        lines.append(f"{key}: {jsonish(value)}")
    lines.append("---")
    return "\n".join(lines)


def parse_jsonish(value: str) -> Any:
    value = value.strip()
    if value == "":
        return ""
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        low = value.lower()
        if low == "null":
            return None
        if low == "true":
            return True
        if low == "false":
            return False
        if re.fullmatch(r"-?\d+", value):
            return int(value)
        if re.fullmatch(r"-?\d+\.\d+", value):
            return float(value)
        return value.strip('"')


def parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    lines = text.splitlines()
    if len(lines) < 3 or lines[0].strip() != "---":
        return {}, text
    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end = i
            break
    if end is None:
        return {}, text
    meta: dict[str, Any] = {}
    for line in lines[1:end]:
        if not line.strip() or ":" not in line:
            continue
        key, raw = line.split(":", 1)
        meta[key.strip()] = parse_jsonish(raw)
    body = "\n".join(lines[end + 1 :]).lstrip("\n")
    return meta, body


def render_bullets(value: Any) -> str:
    if isinstance(value, list):
        return "\n".join(f"- {item}" for item in value) if value else "- None"
    if isinstance(value, str) and value.strip():
        return value.strip()
    return "- None"


def render_table(rows: list[dict[str, Any]], columns: list[tuple[str, str]]) -> str:
    header = "| " + " | ".join(label for label, _ in columns) + " |"
    sep = "| " + " | ".join("---" for _ in columns) + " |"
    body = []
    for row in rows or []:
        body.append("| " + " | ".join(str(row.get(key, "")) for _, key in columns) + " |")
    if not body:
        body.append("| " + " | ".join("" for _ in columns) + " |")
    return "\n".join([header, sep, *body])


def render_worklog_body(payload: dict[str, Any]) -> str:
    mode = payload["mode"]
    sections = payload.get("sections", {})
    if mode == "dev":
        return "\n\n".join(
            [
                "## Goal\n\n" + (sections.get("goal") or ""),
                "## Completed\n\n" + render_bullets(sections.get("completed")),
                "## Key decisions\n\n"
                + render_table(sections.get("key_decisions", []), [("Decision", "decision"), ("Why", "why"), ("Alternatives rejected", "alternatives")]),
                "## Learned / experience candidates\n\n" + render_bullets(sections.get("learned")),
                "## Remaining TODOs\n\n" + render_bullets(sections.get("remaining_todos")),
                "## References\n\n" + render_bullets(sections.get("references")),
            ]
        )
    if mode == "read":
        return "\n\n".join(
            [
                "## Reading goal\n\n" + (sections.get("reading_goal") or ""),
                "## Entry points and path\n\n" + render_bullets(sections.get("entry_points")),
                "## One-sentence mental model\n\n" + (sections.get("mental_model") or ""),
                "## Key findings\n\n" + render_bullets(sections.get("key_findings")),
                "## Open questions / where to resume\n\n" + render_bullets(sections.get("open_questions")),
                "## Evidence\n\n" + render_bullets(sections.get("evidence")),
                "## Follow-on output\n\n" + render_bullets(sections.get("follow_on_output")),
            ]
        )
    if mode == "debug-session":
        return "\n\n".join(
            [
                "## Prior sessions\n\n" + render_bullets(sections.get("prior_sessions")),
                "## Progress in this session\n\n" + render_bullets(sections.get("progress")),
                "## Current status\n\n" + (sections.get("current_status") or ""),
                "## Resume here next time\n\n" + render_bullets(sections.get("resume_here")),
                "## Hypothesis summary\n\n"
                + render_table(sections.get("hypothesis_summary", []), [("Hypothesis", "hypothesis"), ("Status", "status"), ("Evidence", "evidence")]),
                "## Experience candidates\n\n" + render_bullets(sections.get("experience_candidates")),
            ]
        )
    return "\n\n".join(
        [
            "## Timeline\n\n" + render_bullets(sections.get("timeline")),
            "## Key decisions\n\n"
            + render_table(sections.get("key_decisions", []), [("Time", "time"), ("Decision", "decision"), ("Why", "why")]),
            "## Outputs\n\n" + render_outputs(sections.get("outputs", {})),
            "## Experience candidates\n\n" + render_bullets(sections.get("experience_candidates")),
        ]
    )


def render_outputs(outputs: dict[str, Any]) -> str:
    parts = []
    for label, key in [("Code", "code"), ("Knowledge", "knowledge"), ("Remaining", "remaining")]:
        parts.append(f"- {label}: {outputs.get(key, '')}".rstrip())
    return "\n".join(parts)


def build_worklog_frontmatter(payload: dict[str, Any], worklog_id: str, project: str) -> dict[str, Any]:
    mode = payload["mode"]
    frontmatter: dict[str, Any] = {
        "id": worklog_id,
        "mode": mode,
        "project": project,
        "project_path": payload["project_path"],
        "title": payload["title"],
        "started_at": payload["started_at"],
        "duration_minutes": payload["duration_minutes"],
        "status": payload["status"],
        "tags": payload.get("tags", []),
    }
    optional = ["ended_at", "produced_experience_ids"]
    for key in optional:
        if key in payload:
            frontmatter[key] = payload[key]
    if mode == "dev":
        frontmatter.update(
            {
                "branch": payload.get("branch"),
                "commits": payload.get("commits", []),
                "files_changed": payload.get("files_changed", []),
                "loc": payload.get("loc", {"added": 0, "deleted": 0}),
                "pr_url": payload.get("pr_url"),
            }
        )
    elif mode == "read":
        frontmatter.update(
            {
                "read_type": payload.get("read_type"),
                "target": payload.get("target"),
                "target_version": payload.get("target_version"),
                "completion": payload.get("completion"),
            }
        )
    elif mode == "debug-session":
        frontmatter.update(
            {
                "debug_id": payload.get("debug_id"),
                "session_number": payload.get("session_number"),
                "linked_debug_doc": payload.get("linked_debug_doc"),
            }
        )
    elif mode == "mixed":
        frontmatter.update(
            {
                "original_goal": payload.get("original_goal"),
                "final_outcome": payload.get("final_outcome"),
                "involved": payload.get("involved", []),
                "primary_type": payload.get("primary_type"),
            }
        )
    return frontmatter


def build_worklog_entry(frontmatter: dict[str, Any], relative_path: str) -> dict[str, Any]:
    commits = frontmatter.get("commits") or []
    commit_hashes = []
    for item in commits:
        if isinstance(item, dict):
            commit_hashes.append(item.get("hash"))
        else:
            commit_hashes.append(item)
    return {
        "id": frontmatter["id"],
        "date": date_only(frontmatter["started_at"]),
        "project": frontmatter["project"],
        "mode": frontmatter["mode"],
        "title": frontmatter["title"],
        "tags": frontmatter.get("tags", []),
        "duration_minutes": frontmatter["duration_minutes"],
        "status": frontmatter["status"],
        "file": relative_path,
        "debug_id": frontmatter.get("debug_id"),
        "session_number": frontmatter.get("session_number"),
        "linked_debug_doc": frontmatter.get("linked_debug_doc"),
        "commits": [item for item in commit_hashes if item],
        "produced_experience_ids": frontmatter.get("produced_experience_ids", []),
    }


def validate_payload(payload: dict[str, Any]) -> None:
    missing = [key for key in ["mode", "project_path", "title", "started_at", "duration_minutes", "status"] if key not in payload]
    if missing:
        raise SystemExit(f"missing keys: {', '.join(missing)}")
    if payload["mode"] not in VALID_MODES:
        raise SystemExit(f"invalid mode: {payload['mode']}")
    if payload["status"] not in WORKLOG_STATUSES:
        raise SystemExit(f"invalid status: {payload['status']}")
    if not isinstance(payload.get("tags", []), list):
        raise SystemExit("tags must be an array")


def ensure_relative(path: Path, root: Path) -> str:
    return "./" + path.relative_to(root).as_posix()


def parse_worklog_file(path: Path, root: Path) -> dict[str, Any]:
    meta, _ = parse_frontmatter(path.read_text(encoding="utf-8"))
    entry = build_worklog_entry(meta, ensure_relative(path, root))
    return entry


def parse_meta_value(raw: str) -> Any:
    raw = raw.strip()
    if raw.startswith("[") and raw.endswith("]"):
        inner = raw[1:-1].strip()
        if not inner:
            return []
        return [part.strip().strip('"\'') for part in inner.split(",") if part.strip()]
    if raw in {"null", "None"}:
        return None
    if raw in {"true", "false"}:
        return raw == "true"
    if re.fullmatch(r"-?\d+", raw):
        return int(raw)
    return raw.strip('"\'')


def parse_experience_entries(root: Path) -> list[dict[str, Any]]:
    path = root / "EXPERIENCES.md"
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8")
    pattern = re.compile(r"<!-- exp-meta:\n(.*?)\n-->\n\n### (.*?)(?: \{#(exp-[^}]+)\})?\n\n(.*?)(?=\n<!-- exp-meta:|\n## \d{4}-\d{2}-\d{2}\n|\Z)", re.S)
    entries = []
    for match in pattern.finditer(text):
        meta_block, title_line, anchor, body = match.groups()
        meta: dict[str, Any] = {}
        for line in meta_block.splitlines():
            if not line.strip() or ":" not in line:
                continue
            key, raw = line.split(":", 1)
            meta[key.strip()] = parse_meta_value(raw)
        exp_id = meta.get("id") or anchor
        clean_title = re.sub(r"^~~|~~$", "", title_line).strip()
        entries.append(
            {
                "id": exp_id,
                "date": re.search(r"exp-(\d{4}-\d{2}-\d{2})-", exp_id).group(1) if exp_id else None,
                "title": clean_title,
                "title_line": title_line,
                "body": body.strip(),
                "meta": meta,
            }
        )
    return entries


def render_experience_entry(entry: dict[str, Any]) -> str:
    meta = entry["meta"]
    meta_lines = ["<!-- exp-meta:"]
    ordered_keys = [
        "id",
        "tags",
        "project",
        "confidence",
        "status",
        "verified_against",
        "last_verified_at",
        "supersedes",
        "superseded_by",
        "pinned",
        "deprecated_at",
        "deprecated_reason",
        "search_keywords",
        "ref_count",
        "source_worklog_id",
    ]
    for key in ordered_keys:
        meta_lines.append(f"{key}: {meta_value(meta.get(key))}")
    meta_lines.append("-->")
    title_line = entry.get("title_line") or entry["title"]
    anchor = entry["id"]
    return "\n".join(
        [
            *meta_lines,
            "",
            f"### {title_line} {{#{anchor}}}",
            "",
            entry["body"].strip(),
            "",
        ]
    ).rstrip() + "\n"


def meta_value(value: Any) -> str:
    if isinstance(value, list):
        return "[" + ", ".join(str(item) for item in value) + "]"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if value is None:
        return "null"
    return str(value)


def render_experiences_md(entries: list[dict[str, Any]]) -> str:
    entries = sorted(entries, key=lambda item: (item["date"], item["id"]), reverse=True)
    tag_counter = Counter()
    for entry in entries:
        if entry["meta"].get("status", "active") == "active":
            for tag in entry["meta"].get("tags", []):
                tag_counter[tag] += 1
    lines = [
        "# Experience Library",
        "",
        "> Newest first. Keep original wording when deprecating. Mark stale or wrong content with `~~...~~` and add a reason.",
        "",
        "## Tag index",
    ]
    if tag_counter:
        lines.append("- " + " · ".join(f"`#{tag}` ({count})" for tag, count in sorted(tag_counter.items())))
    else:
        lines.append("- None")
    lines.extend(["", "---", ""])
    current_date = None
    for entry in entries:
        if entry["date"] != current_date:
            current_date = entry["date"]
            lines.extend([f"## {current_date}", ""])
        lines.append(render_experience_entry(entry).rstrip())
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def find_anchor_line(text: str, anchor: str) -> int | None:
    target = f"{{#{anchor}}}"
    for i, line in enumerate(text.splitlines(), start=1):
        if target in line:
            return i
    return None


def render_index_md(worklogs: list[dict[str, Any]]) -> str:
    ordered = sorted(worklogs, key=lambda item: (item["date"], item["id"]), reverse=True)
    lines = ["# Work Log Index", ""]
    current_date = None
    for item in ordered:
        if item["date"] != current_date:
            current_date = item["date"]
            lines.extend([f"## {current_date}", ""])
        duration = human_duration(item.get("duration_minutes", 0))
        lines.append(
            f"- `{item['id']}` {item['mode']} · {item['project']} · {item['title']} · {duration} · {item['status']}"
        )
    return "\n".join(lines).rstrip() + "\n"


def human_duration(minutes: int) -> str:
    hours, mins = divmod(int(minutes or 0), 60)
    if hours and mins:
        return f"{hours}h{mins:02d}m"
    if hours:
        return f"{hours}h"
    return f"{mins}m"


def refresh_debug_sessions(worklogs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for item in worklogs:
        debug_id = item.get("debug_id")
        if debug_id:
            grouped.setdefault(debug_id, []).append(item)
    sessions = []
    for debug_id, items in grouped.items():
        ordered = sorted(items, key=lambda item: (item["date"], item["id"]))
        sessions.append(
            {
                "debug_id": debug_id,
                "title": ordered[-1]["title"],
                "status": "in_progress" if ordered[-1]["status"] in {"partial", "paused", "blocked"} else ordered[-1]["status"],
                "session_count": len(ordered),
                "first_seen": ordered[0]["date"],
                "last_seen": ordered[-1]["date"],
                "worklog_ids": [item["id"] for item in ordered],
                "linked_debug_doc": None,
            }
        )
    return sorted(sessions, key=lambda item: item["last_seen"], reverse=True)


def compute_stats(worklogs: list[dict[str, Any]], experiences: list[dict[str, Any]]) -> dict[str, Any]:
    by_tag = Counter()
    by_project = Counter()
    by_status = Counter()
    by_mode = Counter()
    for item in worklogs:
        by_project[item["project"]] += 1
        by_mode[item["mode"]] += 1
        for tag in item.get("tags", []):
            by_tag[tag] += 1
    for item in experiences:
        by_status[item.get("status", "active")] += 1
        for tag in item.get("tags", []):
            by_tag[tag] += 1
    return {
        "by_tag": dict(sorted(by_tag.items())),
        "by_project": dict(sorted(by_project.items())),
        "by_status": dict(sorted(by_status.items())),
        "by_mode": dict(sorted(by_mode.items())),
    }


def build_experience_record(entry: dict[str, Any], source_map: dict[str, dict[str, Any]], line_number: int | None) -> dict[str, Any]:
    meta = entry["meta"]
    source_match = re.search(r"\*\*Source\*\*: \[worklog\]\(([^)]+)\)", entry["body"])
    source_path = source_match.group(1) if source_match else None
    source_worklog_id = None
    if source_path:
        normalized = source_path if source_path.startswith("./") else f"./{source_path.lstrip('./')}"
        for worklog in source_map.values():
            if worklog["file"] == normalized:
                source_worklog_id = worklog["id"]
                break
    summary = entry["body"].splitlines()[0].strip() if entry["body"].strip() else ""
    return {
        "id": entry["id"],
        "title": entry["title"],
        "summary": summary,
        "tags": meta.get("tags", []),
        "search_keywords": meta.get("search_keywords", meta.get("tags", [])),
        "project": meta.get("project"),
        "confidence": meta.get("confidence", "medium"),
        "status": meta.get("status", "active"),
        "date": entry["date"],
        "location": {"file": "EXPERIENCES.md", "anchor": entry["id"], "line": line_number},
        "source_worklog_id": source_worklog_id,
        "verified_against": meta.get("verified_against"),
        "last_verified_at": meta.get("last_verified_at"),
        "supersedes": meta.get("supersedes"),
        "superseded_by": meta.get("superseded_by"),
        "ref_count": int(meta.get("ref_count", 0) or 0),
        "pinned": bool(meta.get("pinned", False)),
        "deprecated_at": meta.get("deprecated_at"),
        "deprecated_reason": meta.get("deprecated_reason"),
    }


def reindex(root: Path) -> dict[str, Any]:
    ensure_root(root)
    worklog_files = sorted(root.glob("*/*/*.md"))
    worklogs = [parse_worklog_file(path, root) for path in worklog_files if path.name not in {"INDEX.md", "EXPERIENCES.md"}]
    source_map = {item["id"]: item for item in worklogs}
    experience_entries = parse_experience_entries(root)
    experiences_md = render_experiences_md(experience_entries)
    (root / "EXPERIENCES.md").write_text(experiences_md, encoding="utf-8")
    experiences = []
    for entry in experience_entries:
        line = find_anchor_line(experiences_md, entry["id"])
        experiences.append(build_experience_record(entry, source_map, line))
    index = {
        "version": 1,
        "updated_at": iso_now(),
        "experiences": experiences,
        "worklogs": sorted(worklogs, key=lambda item: (item["date"], item["id"]), reverse=True),
        "snippets": [],
        "debug_sessions": refresh_debug_sessions(worklogs),
        "stats": compute_stats(worklogs, experiences),
    }
    write_index_json(root, index)
    (root / "INDEX.md").write_text(render_index_md(worklogs), encoding="utf-8")
    return index


def normalize_experience(exp: dict[str, Any], worklog_id: str, project: str, worklog_relpath: str, date: str, exp_id: str) -> dict[str, Any]:
    status = exp.get("status", "active")
    confidence = exp.get("confidence", "medium")
    if status not in EXPERIENCE_STATUSES:
        raise SystemExit(f"invalid experience status: {status}")
    if confidence not in CONFIDENCE_LEVELS:
        raise SystemExit(f"invalid confidence: {confidence}")
    body = (exp.get("body") or "").strip()
    source_line = exp.get("source_line") or f"**Source**: [worklog]({worklog_relpath})"
    if source_line not in body:
        body = (body + "\n\n" + source_line).strip()
    title = exp["title"].strip()
    title_line = title
    if status in {"deprecated", "wrong"} and not title.startswith("~~"):
        title_line = f"~~{title}~~"
    return {
        "id": exp_id,
        "date": date,
        "title": title,
        "title_line": title_line,
        "body": body,
        "meta": {
            "id": exp_id,
            "tags": exp.get("tags", []),
            "project": exp.get("project", project),
            "confidence": confidence,
            "status": status,
            "verified_against": exp.get("verified_against"),
            "last_verified_at": exp.get("last_verified_at", date),
            "supersedes": exp.get("supersedes"),
            "superseded_by": exp.get("superseded_by"),
            "pinned": bool(exp.get("pinned", False)),
            "deprecated_at": exp.get("deprecated_at"),
            "deprecated_reason": exp.get("deprecated_reason"),
            "search_keywords": exp.get("search_keywords", []),
            "ref_count": int(exp.get("ref_count", 0) or 0),
            "source_worklog_id": worklog_id,
        },
    }
