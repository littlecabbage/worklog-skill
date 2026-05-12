---
name: worklog
description: Persist and retrieve Claude Code work logs and reusable experiences under the current project's .worklog directory by default. Use when the user wants to record a coding session, source-reading session, debug session, or mixed session; when a task mixes development, reading, and debugging; when adding, deprecating, or superseding experience entries; or when searching prior work via index.json and jq.
---

# Worklog

## Default workflow: context-first, draft-first
1. Infer the mode from current context before asking the user to fill fields.
2. Draft a save-ready worklog from the conversation, workspace, git state, changed files, commands run, errors, decisions, and verification results that are visible to you.
3. Show one compact confirmation containing:
   - inferred `mode`, `mode_confidence`, and 2-5 evidence bullets
   - generated title, status, tags, and duration if available
   - 3-6 session summary bullets
   - 0-2 experience candidates marked as pending
4. Ask only one question by default: "Save this draft, edit mode/title/tags, or discard it?"
5. Write the session log to `<project-root>/.worklog/YYYY-MM-DD/<task-slug>.md` only after confirmation.
6. Update `INDEX.md` in newest-first order.
7. Promote reusable findings into `EXPERIENCES.md` and `index.json` only when the user explicitly confirms the experience candidates.
8. Search `index.json` with `jq` before reading older markdown in full.

Do not start `/worklog` by asking for title, status, tags, or mode. Generate the draft first. Ask a follow-up only when the draft cannot be made coherent from context or when mode confidence is low.

## Interaction modes
- `/worklog`: default compact flow. Infer, draft, then ask once for save/edit/discard.
- `/worklog <mode>`: use the requested mode, still draft first and ask once.
- `/worklog edit` or `/worklog guided`: detailed mode for users who explicitly want to revise fields section by section.
- Low confidence: ask one targeted choice, such as "Is this mainly `read` or `debug-session`?", then continue with a draft.

## Mode selection
- `dev`: the main outcome is code changes.
- `read`: the main outcome is understanding code, APIs, or architecture.
- `debug-session`: the main outcome is diagnosing a bug, including work that spans more than one session.
- `mixed`: the session pivots between reading, debugging, and implementation; preserve the pivots and the final outcome.

Score every candidate mode from evidence:
- changed files, commits, tests, or implementation decisions point to `dev`
- source reading, API exploration, architecture notes, or explanations point to `read`
- errors, reproduction steps, hypotheses, root cause, or verification of a fix point to `debug-session`
- strong evidence from multiple categories points to `mixed`

Prefer `mixed` as the fallback instead of introducing a new general mode. Include `mode_confidence` as `high`, `medium`, or `low`, and include `mode_evidence` in the JSON payload when saving.

## Record rules
- Default to project-local storage. Resolve the root as the nearest git repository's `.worklog/`; if no git root exists, use the current directory's `.worklog/`.
- Use `--root ~/.claude/worklog` only when the user explicitly asks for a global local store; global stores keep the old `<project-slug>/YYYY-MM-DD/<task-slug>.md` grouping.
- Keep human-readable markdown newest-first.
- Keep `index.json` as the machine lookup layer.
- Preserve links to the original worklog and to the exact markdown anchor or line range.
- When an experience becomes wrong or stale, keep the original wording and mark it with `~~...~~`, then set `status: deprecated` or `status: wrong` and add a reason.
- Keep entries short and factual.
- Separate observation, decision, and inference.
- Treat experience candidates as pending in the draft. Do not write them to `EXPERIENCES.md` unless the user says to save all, save selected candidates, or otherwise confirms them.
- Prefer automatic defaults over asking: `status=partial`, `duration_minutes=0`, and `mixed` fallback are acceptable when exact values are unavailable.

## Retrieval
- Use `jq` to shortlist candidate IDs from `index.json`.
- Read only the matching markdown section or line range.
- Prefer `active` and `high` confidence entries first.
- Rebuild `index.json` from markdown metadata if it drifts.

## Scripts
- Run `python3 scripts/init_worklog.py` to initialize the current project's `.worklog/`.
- Run `python3 scripts/finish_worklog.py --input <file.json>` or pipe JSON on stdin to append one worklog, update `INDEX.md`, update `EXPERIENCES.md`, and refresh `index.json`.
- The script accepts draft-first payloads with missing optional fields and fills safe defaults before validation. Still provide richer fields when context supports them.
- Run `python3 scripts/reindex_worklog.py` to rebuild `INDEX.md` and `index.json` from markdown.
- Use JSON input for deterministic writes. Prefer generating the JSON payload in-memory or through a temp file rather than editing markdown manually.
- Pass `--root ~/.claude/worklog` when a global machine-local worklog is intentionally desired.

## Reference
- See `references/worklog-format.md` for the exact schema, metadata comment format, and jq query patterns.
- See `references/worklog-format.zh.md` for a Chinese version of the same reference.
