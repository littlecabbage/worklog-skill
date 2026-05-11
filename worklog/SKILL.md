---
name: worklog
description: Persist and retrieve Claude Code work logs and reusable experiences under ~/.claude/worklog. Use when the user wants to record a coding session, source-reading session, debug session, or mixed session; when a task mixes development, reading, and debugging; when adding, deprecating, or superseding experience entries; or when searching prior work via index.json and jq.
---

# Worklog

## Workflow
1. Choose the mode: `dev`, `read`, `debug-session`, or `mixed`.
2. Collect session facts: project path, title, status, start/end time, duration, tags, and mode-specific fields.
3. Write the session log to `~/.claude/worklog/<project-slug>/YYYY-MM-DD/<task-slug>.md`.
4. Update `INDEX.md` in newest-first order.
5. Promote reusable findings into `EXPERIENCES.md` and `index.json` when they are likely to be referenced again.
6. Search `index.json` with `jq` before reading older markdown in full.

## Mode selection
- `dev`: the main outcome is code changes.
- `read`: the main outcome is understanding code, APIs, or architecture.
- `debug-session`: the main outcome is diagnosing a bug, including work that spans more than one session.
- `mixed`: the session pivots between reading, debugging, and implementation; preserve the pivots and the final outcome.

## Record rules
- Keep human-readable markdown newest-first.
- Keep `index.json` as the machine lookup layer.
- Preserve links to the original worklog and to the exact markdown anchor or line range.
- When an experience becomes wrong or stale, keep the original wording and mark it with `~~...~~`, then set `status: deprecated` or `status: wrong` and add a reason.
- Keep entries short and factual.
- Separate observation, decision, and inference.

## Retrieval
- Use `jq` to shortlist candidate IDs from `index.json`.
- Read only the matching markdown section or line range.
- Prefer `active` and `high` confidence entries first.
- Rebuild `index.json` from markdown metadata if it drifts.

## Scripts
- Run `python3 scripts/init_worklog.py` to initialize `~/.claude/worklog`.
- Run `python3 scripts/finish_worklog.py --input <file.json>` or pipe JSON on stdin to append one worklog, update `INDEX.md`, update `EXPERIENCES.md`, and refresh `index.json`.
- Run `python3 scripts/reindex_worklog.py` to rebuild `INDEX.md` and `index.json` from markdown.
- Use JSON input for deterministic writes. Prefer generating the JSON payload in-memory or through a temp file rather than editing markdown manually.

## Reference
- See `references/worklog-format.md` for the exact schema, metadata comment format, and jq query patterns.
- See `references/worklog-format.zh.md` for a Chinese version of the same reference.
