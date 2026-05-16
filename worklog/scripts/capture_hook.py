#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from worklog_lib import (
    current_session_dir,
    iso_now,
    redact_path,
    truncate_field,
)

PROMPT_LIMIT = 500
TARGET_LIMIT = 256
EXCERPT_LIMIT = 300

KNOWN_EVENTS = {"user_prompt_submit", "post_tool_use", "stop"}


def read_last_assistant_excerpt(transcript_path: Any) -> str:
    if not isinstance(transcript_path, str) or not transcript_path:
        return ""
    try:
        path = Path(transcript_path)
        if not path.exists():
            return ""
        with path.open("r", encoding="utf-8") as fh:
            lines = fh.readlines()
    except OSError:
        return ""
    for line in reversed(lines):
        stripped = line.strip()
        if not stripped:
            continue
        try:
            record = json.loads(stripped)
        except json.JSONDecodeError:
            continue
        if record.get("type") != "assistant":
            continue
        message = record.get("message") or {}
        content = message.get("content", "")
        if isinstance(content, list):
            parts: list[str] = []
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    text = block.get("text")
                    if isinstance(text, str):
                        parts.append(text)
            content = "\n".join(parts)
        if isinstance(content, str) and content.strip():
            return content
    return ""


def extract_target(tool_input: Any) -> str:
    if not isinstance(tool_input, dict):
        return ""
    for key in ("file_path", "path", "command", "pattern", "url", "notebook_path"):
        value = tool_input.get(key)
        if isinstance(value, str) and value:
            return value
    return ""


def build_event(event_type: str, payload: dict[str, Any]) -> dict[str, Any] | None:
    ts = iso_now()
    sid = payload.get("session_id", "")
    if event_type == "user_prompt_submit":
        prompt = payload.get("prompt", "")
        return {
            "ts": ts,
            "sid": sid,
            "type": "prompt",
            "display": truncate_field(prompt, PROMPT_LIMIT),
        }
    if event_type == "post_tool_use":
        tool_input = payload.get("tool_input") or {}
        tool_response = payload.get("tool_response")
        target_raw = extract_target(tool_input)
        target = redact_path(target_raw)
        target = truncate_field(target, TARGET_LIMIT)
        ok = True
        if isinstance(tool_response, dict):
            err = tool_response.get("error")
            ok = err in (None, "", False)
        return {
            "ts": ts,
            "sid": sid,
            "type": "tool",
            "name": payload.get("tool_name", ""),
            "target": target,
            "ok": ok,
        }
    if event_type == "stop":
        excerpt = read_last_assistant_excerpt(payload.get("transcript_path"))
        return {
            "ts": ts,
            "sid": sid,
            "type": "stop",
            "excerpt": truncate_field(excerpt, EXCERPT_LIMIT),
        }
    return None


def main() -> None:
    if os.environ.get("WORKLOG_HOOK_ACTIVE") == "1":
        return

    if len(sys.argv) < 2:
        return
    event_type = sys.argv[1]
    if event_type not in KNOWN_EVENTS:
        return

    try:
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw else None
    except (json.JSONDecodeError, OSError):
        return
    if not isinstance(payload, dict):
        return

    sid = payload.get("session_id")
    cwd = payload.get("cwd")
    if not isinstance(sid, str) or not sid:
        return
    if not isinstance(cwd, str) or not cwd:
        return

    event = build_event(event_type, payload)
    if event is None:
        return

    try:
        draft_dir = current_session_dir(cwd, sid)
        draft_dir.mkdir(parents=True, exist_ok=True)
        with (draft_dir / "events.jsonl").open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(event, ensure_ascii=False) + "\n")
    except OSError:
        return


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
    sys.exit(0)
