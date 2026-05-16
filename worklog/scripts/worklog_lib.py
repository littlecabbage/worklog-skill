#!/usr/bin/env python3
from __future__ import annotations

import fnmatch
import json
import os
import re
import subprocess
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

GLOBAL_ROOT = Path.home() / ".claude" / "worklog"
WORKLOG_DIR_NAME = ".worklog"
DEFAULT_ROOT = Path(WORKLOG_DIR_NAME)
VALID_MODES = {"dev", "read", "debug-session", "mixed"}
READ_TYPES = {"survey", "deep-dive", "hunt", "compare"}
PRIMARY_TYPES = {"dev", "read", "debug"}
WORKLOG_STATUSES = {"completed", "partial", "paused", "blocked", "abandoned"}
EXPERIENCE_STATUSES = {"active", "deprecated", "wrong", "evolving"}
CONFIDENCE_LEVELS = {"high", "medium", "low"}
SUPPORTED_LANGUAGES = {"en", "zh"}
DEFAULT_LANGUAGE = "zh"
DEFAULT_TAGS_BY_MODE = {
    "dev": ["dev"],
    "read": ["read"],
    "debug-session": ["debug"],
    "mixed": ["mixed"],
}


def find_git_root(start: Path | None = None) -> Path | None:
    current = (start or Path.cwd()).expanduser()
    if current.is_file():
        current = current.parent
    current = current.resolve()
    for candidate in [current, *current.parents]:
        if (candidate / ".git").exists():
            return candidate
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=current,
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    output = result.stdout.strip()
    return Path(output).expanduser().resolve() if output else None


def default_project_root(start: str | Path | None = None) -> Path:
    start_path = Path(start).expanduser() if start else Path.cwd()
    if start and not start_path.exists():
        start_path = Path.cwd()
    git_root = find_git_root(start_path)
    base = git_root or (start_path if start_path.is_dir() else start_path.parent)
    return (base / WORKLOG_DIR_NAME).resolve()


def root_path(value: str | None = None, start: str | Path | None = None) -> Path:
    return Path(value).expanduser() if value else default_project_root(start)


def ensure_root(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "archive").mkdir(exist_ok=True)
    if not (root / "INDEX.md").exists():
        (root / "INDEX.md").write_text(f"# {t(DEFAULT_LANGUAGE, 'index.title')}\n", encoding="utf-8")
    if not (root / "EXPERIENCES.md").exists():
        (root / "EXPERIENCES.md").write_text(
            f"# {t(DEFAULT_LANGUAGE, 'exp.title')}\n\n> {t(DEFAULT_LANGUAGE, 'exp.preamble')}\n",
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
    cleaned = re.sub(r"[^\w._-]+", "-", value.strip().lower(), flags=re.UNICODE)
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


def set_default_if_blank(data: dict[str, Any], key: str, value: Any) -> None:
    if key not in data or is_blank(data.get(key)):
        data[key] = value


def ensure_sections(payload: dict[str, Any]) -> dict[str, Any]:
    sections = payload.get("sections")
    if not isinstance(sections, dict):
        sections = {}
        payload["sections"] = sections
    return sections


def default_debug_id(payload: dict[str, Any]) -> str:
    day = date_only(payload["started_at"])
    return f"dbg-{day}-{slugify(payload['title'])}"


def first_valid_primary_type(values: Any) -> str | None:
    if not isinstance(values, list):
        return None
    normalized = ["debug" if item == "debug-session" else item for item in values]
    for candidate in ("debug", "dev", "read"):
        if candidate in normalized:
            return candidate
    return None


def apply_payload_defaults(payload: dict[str, Any]) -> dict[str, Any]:
    set_default_if_blank(payload, "mode", "mixed")
    set_default_if_blank(payload, "project_path", os.getcwd())
    set_default_if_blank(payload, "title", "Worklog draft")
    set_default_if_blank(payload, "started_at", iso_now())
    set_default_if_blank(payload, "duration_minutes", 0)
    set_default_if_blank(payload, "status", "partial")
    set_default_if_blank(payload, "language", DEFAULT_LANGUAGE)

    mode = payload.get("mode")
    if not isinstance(payload.get("tags"), list):
        payload["tags"] = []
    if not payload["tags"] and mode in DEFAULT_TAGS_BY_MODE:
        payload["tags"] = list(DEFAULT_TAGS_BY_MODE[mode])

    sections = ensure_sections(payload)
    if mode == "dev":
        set_default_if_blank(sections, "goal", payload["title"])
        sections.setdefault("completed", [])
        sections.setdefault("key_decisions", [])
        sections.setdefault("learned", sections.get("experience_candidates", []))
        sections.setdefault("remaining_todos", [])
        sections.setdefault("references", [])
        payload.setdefault("commits", [])
        payload.setdefault("files_changed", [])
        payload.setdefault("loc", {"added": 0, "deleted": 0})
    elif mode == "read":
        set_default_if_blank(payload, "read_type", "survey")
        set_default_if_blank(payload, "target", project_slug(payload["project_path"], payload.get("project")))
        set_default_if_blank(payload, "target_version", "unknown")
        set_default_if_blank(payload, "completion", 0)
        set_default_if_blank(sections, "reading_goal", payload["title"])
        sections.setdefault("entry_points", [])
        set_default_if_blank(sections, "mental_model", "Pending confirmation.")
        sections.setdefault("key_findings", [])
        sections.setdefault("open_questions", [])
        sections.setdefault("evidence", [])
        sections.setdefault("follow_on_output", [])
    elif mode == "debug-session":
        set_default_if_blank(payload, "debug_id", default_debug_id(payload))
        sections.setdefault("prior_sessions", [])
        sections.setdefault("progress", [])
        set_default_if_blank(sections, "current_status", "Pending confirmation.")
        sections.setdefault("resume_here", [])
        sections.setdefault("hypothesis_summary", [])
        sections.setdefault("experience_candidates", [])
    elif mode == "mixed":
        set_default_if_blank(payload, "original_goal", payload["title"])
        set_default_if_blank(payload, "final_outcome", "Pending confirmation.")
        if not isinstance(payload.get("involved"), list) or not payload["involved"]:
            inferred = [tag for tag in payload.get("tags", []) if tag in {"dev", "read", "debug"}]
            payload["involved"] = inferred or ["dev"]
        set_default_if_blank(payload, "primary_type", first_valid_primary_type(payload.get("involved")) or "dev")
        sections.setdefault("timeline", [])
        sections.setdefault("key_decisions", [])
        outputs = sections.get("outputs")
        if not isinstance(outputs, dict):
            outputs = {}
            sections["outputs"] = outputs
        set_default_if_blank(outputs, "code", "None")
        set_default_if_blank(outputs, "knowledge", "Pending confirmation.")
        set_default_if_blank(outputs, "remaining", "Pending confirmation.")
        sections.setdefault("experience_candidates", [])
    return payload


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
    lang = payload.get("language")
    if mode == "dev":
        return "\n\n".join(
            [
                f"## {t(lang, 'h.goal')}\n\n" + (sections.get("goal") or ""),
                f"## {t(lang, 'h.completed')}\n\n" + render_bullets(sections.get("completed")),
                f"## {t(lang, 'h.key_decisions')}\n\n"
                + render_table(
                    sections.get("key_decisions", []),
                    [
                        (t(lang, "col.decision"), "decision"),
                        (t(lang, "col.why"), "why"),
                        (t(lang, "col.alternatives"), "alternatives"),
                    ],
                ),
                f"## {t(lang, 'h.learned')}\n\n" + render_bullets(sections.get("learned")),
                f"## {t(lang, 'h.remaining_todos')}\n\n" + render_bullets(sections.get("remaining_todos")),
                f"## {t(lang, 'h.references')}\n\n" + render_bullets(sections.get("references")),
            ]
        )
    if mode == "read":
        return "\n\n".join(
            [
                f"## {t(lang, 'h.reading_goal')}\n\n" + (sections.get("reading_goal") or ""),
                f"## {t(lang, 'h.entry_points')}\n\n" + render_bullets(sections.get("entry_points")),
                f"## {t(lang, 'h.mental_model')}\n\n" + (sections.get("mental_model") or ""),
                f"## {t(lang, 'h.key_findings')}\n\n" + render_bullets(sections.get("key_findings")),
                f"## {t(lang, 'h.open_questions')}\n\n" + render_bullets(sections.get("open_questions")),
                f"## {t(lang, 'h.evidence')}\n\n" + render_bullets(sections.get("evidence")),
                f"## {t(lang, 'h.follow_on_output')}\n\n" + render_bullets(sections.get("follow_on_output")),
            ]
        )
    if mode == "debug-session":
        return "\n\n".join(
            [
                f"## {t(lang, 'h.prior_sessions')}\n\n" + render_bullets(sections.get("prior_sessions")),
                f"## {t(lang, 'h.progress')}\n\n" + render_bullets(sections.get("progress")),
                f"## {t(lang, 'h.current_status')}\n\n" + (sections.get("current_status") or ""),
                f"## {t(lang, 'h.resume_here')}\n\n" + render_bullets(sections.get("resume_here")),
                f"## {t(lang, 'h.hypothesis_summary')}\n\n"
                + render_table(
                    sections.get("hypothesis_summary", []),
                    [
                        (t(lang, "col.hypothesis"), "hypothesis"),
                        (t(lang, "col.status"), "status"),
                        (t(lang, "col.evidence"), "evidence"),
                    ],
                ),
                f"## {t(lang, 'h.experience_candidates')}\n\n" + render_bullets(sections.get("experience_candidates")),
            ]
        )
    return "\n\n".join(
        [
            f"## {t(lang, 'h.timeline')}\n\n" + render_bullets(sections.get("timeline")),
            f"## {t(lang, 'h.key_decisions')}\n\n"
            + render_table(
                sections.get("key_decisions", []),
                [
                    (t(lang, "col.time"), "time"),
                    (t(lang, "col.decision"), "decision"),
                    (t(lang, "col.why"), "why"),
                ],
            ),
            f"## {t(lang, 'h.outputs')}\n\n" + render_outputs(sections.get("outputs", {}), lang),
            f"## {t(lang, 'h.experience_candidates')}\n\n" + render_bullets(sections.get("experience_candidates")),
        ]
    )


def render_outputs(outputs: dict[str, Any], language: Any = None) -> str:
    parts = []
    for label_key, value_key in [("label.code", "code"), ("label.knowledge", "knowledge"), ("label.remaining", "remaining")]:
        parts.append(f"- {t(language, label_key)}: {outputs.get(value_key, '')}".rstrip())
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
        "language": normalize_language(payload.get("language")),
    }
    optional = ["ended_at", "produced_experience_ids", "mode_confidence", "mode_evidence", "draft_confirmed"]
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
        "language": normalize_language(frontmatter.get("language")),
    }


def is_blank(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    return False


def require_fields(data: dict[str, Any], fields: list[str], context: str) -> None:
    missing = [field for field in fields if field not in data or is_blank(data.get(field))]
    if missing:
        raise SystemExit(f"{context} requires: {', '.join(missing)}")


def require_list(value: Any, name: str) -> list[Any]:
    if not isinstance(value, list):
        raise SystemExit(f"{name} must be an array")
    return value


def require_dict(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise SystemExit(f"{name} must be an object")
    return value


def validate_experience_inputs(experiences: Any) -> None:
    require_list(experiences, "experiences")
    for index, experience in enumerate(experiences, start=1):
        if not isinstance(experience, dict):
            raise SystemExit(f"experiences[{index}] must be an object")
        require_fields(experience, ["title", "body"], f"experiences[{index}]")
        if "tags" in experience:
            require_list(experience["tags"], f"experiences[{index}].tags")
        if "search_keywords" in experience:
            require_list(experience["search_keywords"], f"experiences[{index}].search_keywords")
        status = experience.get("status", "active")
        confidence = experience.get("confidence", "medium")
        if status not in EXPERIENCE_STATUSES:
            raise SystemExit(f"experiences[{index}].status must be one of: {', '.join(sorted(EXPERIENCE_STATUSES))}")
        if confidence not in CONFIDENCE_LEVELS:
            raise SystemExit(f"experiences[{index}].confidence must be one of: {', '.join(sorted(CONFIDENCE_LEVELS))}")


def validate_payload(payload: dict[str, Any]) -> None:
    apply_payload_defaults(payload)
    require_fields(payload, ["mode", "project_path", "title", "started_at", "duration_minutes", "status"], "worklog payload")
    if payload["mode"] not in VALID_MODES:
        raise SystemExit(f"mode must be one of: {', '.join(sorted(VALID_MODES))}")
    if payload["status"] not in WORKLOG_STATUSES:
        raise SystemExit(f"status must be one of: {', '.join(sorted(WORKLOG_STATUSES))}")
    if payload.get("language") not in SUPPORTED_LANGUAGES:
        raise SystemExit(f"language must be one of: {', '.join(sorted(SUPPORTED_LANGUAGES))}")
    require_list(payload.get("tags", []), "tags")
    try:
        parse_date(payload["started_at"])
    except ValueError as exc:
        raise SystemExit(f"started_at must be ISO 8601: {exc}") from exc
    if not isinstance(payload["duration_minutes"], int) or payload["duration_minutes"] < 0:
        raise SystemExit("duration_minutes must be a non-negative integer")

    sections = require_dict(payload.get("sections", {}), "sections")
    if payload.get("experiences") is not None:
        validate_experience_inputs(payload["experiences"])

    mode = payload["mode"]
    if mode == "dev":
        require_fields(sections, ["goal"], "mode=dev sections")
        if "commits" in payload and not isinstance(payload["commits"], list):
            raise SystemExit("mode=dev commits must be an array")
        if "files_changed" in payload and not isinstance(payload["files_changed"], list):
            raise SystemExit("mode=dev files_changed must be an array")
    elif mode == "read":
        require_fields(payload, ["read_type", "target", "target_version", "completion"], "mode=read")
        if payload["read_type"] not in READ_TYPES:
            raise SystemExit(f"mode=read read_type must be one of: {', '.join(sorted(READ_TYPES))}")
        if not isinstance(payload["completion"], int) or not 0 <= payload["completion"] <= 100:
            raise SystemExit("mode=read completion must be an integer from 0 to 100")
        require_fields(sections, ["reading_goal", "mental_model"], "mode=read sections")
    elif mode == "debug-session":
        require_fields(payload, ["debug_id"], "mode=debug-session")
        if payload.get("session_number") is not None and (not isinstance(payload["session_number"], int) or payload["session_number"] <= 0):
            raise SystemExit("mode=debug-session session_number must be a positive integer")
        require_fields(sections, ["current_status"], "mode=debug-session sections")
    elif mode == "mixed":
        require_fields(payload, ["original_goal", "final_outcome", "primary_type"], "mode=mixed")
        require_list(payload.get("involved", []), "mode=mixed involved")
        if payload["primary_type"] not in PRIMARY_TYPES:
            raise SystemExit(f"mode=mixed primary_type must be one of: {', '.join(sorted(PRIMARY_TYPES))}")
        require_fields(sections, ["timeline"], "mode=mixed sections")
        outputs = require_dict(sections.get("outputs", {}), "mode=mixed sections.outputs")
        require_fields(outputs, ["code", "knowledge", "remaining"], "mode=mixed sections.outputs")


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


def render_experiences_md(entries: list[dict[str, Any]], language: Any = None) -> str:
    entries = sorted(entries, key=lambda item: (item["date"], item["id"]), reverse=True)
    tag_counter = Counter()
    for entry in entries:
        if entry["meta"].get("status", "active") == "active":
            for tag in entry["meta"].get("tags", []):
                tag_counter[tag] += 1
    lines = [
        f"# {t(language, 'exp.title')}",
        "",
        f"> {t(language, 'exp.preamble')}",
        "",
        f"## {t(language, 'exp.tag_index')}",
    ]
    if tag_counter:
        lines.append("- " + " · ".join(f"`#{tag}` ({count})" for tag, count in sorted(tag_counter.items())))
    else:
        lines.append(f"- {t(language, 'exp.none')}")
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


def render_index_md(worklogs: list[dict[str, Any]], language: Any = None) -> str:
    ordered = sorted(worklogs, key=lambda item: (item["date"], item["id"]), reverse=True)
    lines = [f"# {t(language, 'index.title')}", ""]
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


def rebuild_indexes(root: Path, entries: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    ensure_root(root)
    worklog_files = sorted({*root.glob("*/*.md"), *root.glob("*/*/*.md")})
    worklogs = [parse_worklog_file(path, root) for path in worklog_files if path.name not in {"INDEX.md", "EXPERIENCES.md"}]
    source_map = {item["id"]: item for item in worklogs}
    experience_entries = entries if entries is not None else parse_experience_entries(root)
    project_language = majority_language(worklogs)
    experiences_md = render_experiences_md(experience_entries, project_language)
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
    (root / "INDEX.md").write_text(render_index_md(worklogs, project_language), encoding="utf-8")
    return index


def reindex(root: Path) -> dict[str, Any]:
    return rebuild_indexes(root)


def get_experience_by_id(entries: list[dict[str, Any]], experience_id: str) -> dict[str, Any]:
    for entry in entries:
        if entry["id"] == experience_id:
            return entry
    raise SystemExit(f"experience not found: {experience_id}")


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


SENSITIVE_FILENAME_PATTERNS = [
    ".env",
    ".env.*",
    "*secret*",
    "*credential*",
    "*password*",
    "*token*",
    "*.pem",
    "*.key",
    "id_rsa*",
    ".netrc",
]
SENSITIVE_PATH_SEGMENTS = {".ssh", ".aws"}
REDACTED = "<redacted>"
ELLIPSIS = "…"


def redact_path(value: Any) -> Any:
    if not isinstance(value, str) or not value:
        return value
    try:
        candidate = Path(value)
    except (ValueError, OSError):
        return value
    name_lower = candidate.name.lower()
    for pattern in SENSITIVE_FILENAME_PATTERNS:
        if fnmatch.fnmatchcase(name_lower, pattern):
            return REDACTED
    for segment in candidate.parts:
        if segment.lower() in SENSITIVE_PATH_SEGMENTS:
            return REDACTED
    return value


def truncate_field(value: Any, limit: int) -> str:
    if value is None:
        return ""
    text = value if isinstance(value, str) else str(value)
    if limit <= 0 or len(text) <= limit:
        return text
    return text[:limit] + ELLIPSIS


def current_session_dir(cwd: str | Path | None, session_id: str) -> Path:
    return default_project_root(cwd) / "draft" / session_id


def load_session_events(cwd: str | Path | None, session_id: str) -> list[dict[str, Any]]:
    path = current_session_dir(cwd, session_id) / "events.jsonl"
    if not path.exists():
        return []
    events: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        try:
            events.append(json.loads(stripped))
        except json.JSONDecodeError:
            continue
    return events


def archive_draft(cwd: str | Path | None, session_id: str) -> Path | None:
    source = current_session_dir(cwd, session_id)
    if not source.exists():
        return None
    archived_root = source.parent / ".archived"
    archived_root.mkdir(parents=True, exist_ok=True)
    target = archived_root / session_id
    if target.exists():
        target = archived_root / f"{session_id}-{int(datetime.now().timestamp())}"
    source.rename(target)
    return target


I18N: dict[str, dict[str, str]] = {
    "en": {
        "h.goal": "Goal",
        "h.completed": "Completed",
        "h.key_decisions": "Key decisions",
        "h.learned": "Learned / experience candidates",
        "h.remaining_todos": "Remaining TODOs",
        "h.references": "References",
        "h.reading_goal": "Reading goal",
        "h.entry_points": "Entry points and path",
        "h.mental_model": "One-sentence mental model",
        "h.key_findings": "Key findings",
        "h.open_questions": "Open questions / where to resume",
        "h.evidence": "Evidence",
        "h.follow_on_output": "Follow-on output",
        "h.prior_sessions": "Prior sessions",
        "h.progress": "Progress in this session",
        "h.current_status": "Current status",
        "h.resume_here": "Resume here next time",
        "h.hypothesis_summary": "Hypothesis summary",
        "h.experience_candidates": "Experience candidates",
        "h.timeline": "Timeline",
        "h.outputs": "Outputs",
        "col.decision": "Decision",
        "col.why": "Why",
        "col.alternatives": "Alternatives rejected",
        "col.time": "Time",
        "col.hypothesis": "Hypothesis",
        "col.status": "Status",
        "col.evidence": "Evidence",
        "label.code": "Code",
        "label.knowledge": "Knowledge",
        "label.remaining": "Remaining",
        "index.title": "Work Log Index",
        "exp.title": "Experience Library",
        "exp.preamble": "Newest first. Keep original wording when deprecating. Mark stale or wrong content with `~~...~~` and add a reason.",
        "exp.tag_index": "Tag index",
        "exp.none": "None",
    },
    "zh": {
        "h.goal": "目标",
        "h.completed": "完成情况",
        "h.key_decisions": "关键决策",
        "h.learned": "经验候选",
        "h.remaining_todos": "遗留 TODO",
        "h.references": "参考",
        "h.reading_goal": "阅读目标",
        "h.entry_points": "入口与路径",
        "h.mental_model": "一句话心智模型",
        "h.key_findings": "关键发现",
        "h.open_questions": "未解问题 / 下次继续",
        "h.evidence": "引用证据",
        "h.follow_on_output": "衍生产出",
        "h.prior_sessions": "历次会话",
        "h.progress": "本次进展",
        "h.current_status": "当前状态",
        "h.resume_here": "下次从这里继续",
        "h.hypothesis_summary": "假设池摘要",
        "h.experience_candidates": "经验候选",
        "h.timeline": "主线时间线",
        "h.outputs": "产出",
        "col.decision": "决策",
        "col.why": "原因",
        "col.alternatives": "已排除方案",
        "col.time": "时间",
        "col.hypothesis": "假设",
        "col.status": "状态",
        "col.evidence": "证据",
        "label.code": "代码",
        "label.knowledge": "知识",
        "label.remaining": "遗留",
        "index.title": "工作日志索引",
        "exp.title": "经验库",
        "exp.preamble": "最新优先。废弃时保留原文。过期或错误的内容用 `~~...~~` 标记并注明原因。",
        "exp.tag_index": "标签索引",
        "exp.none": "无",
    },
}


def normalize_language(value: Any) -> str:
    if isinstance(value, str) and value in SUPPORTED_LANGUAGES:
        return value
    return DEFAULT_LANGUAGE


def t(language: Any, key: str) -> str:
    lang = normalize_language(language)
    table = I18N.get(lang) or I18N[DEFAULT_LANGUAGE]
    if key in table:
        return table[key]
    return I18N[DEFAULT_LANGUAGE].get(key, key)


def majority_language(worklogs: list[dict[str, Any]]) -> str:
    counts: dict[str, int] = {}
    for item in worklogs:
        lang = normalize_language(item.get("language") if isinstance(item, dict) else None)
        counts[lang] = counts.get(lang, 0) + 1
    if not counts:
        return DEFAULT_LANGUAGE
    return max(SUPPORTED_LANGUAGES, key=lambda lg: (counts.get(lg, 0), lg == DEFAULT_LANGUAGE))
