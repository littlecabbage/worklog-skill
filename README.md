# worklog

[中文说明](README.zh.md)

A shareable Claude Code skill for turning individual working sessions into searchable work logs and reusable engineering knowledge.

`worklog` helps you capture not just what changed, but also what you learned, what you ruled out, and what should be easy to find again later.

## What it does

The skill supports four session modes:
- `dev`
- `read`
- `debug-session`
- `mixed`

By default it writes project-local artifacts under the current repository's `.worklog/` directory:
- `INDEX.md` for human-readable session history
- `EXPERIENCES.md` for reusable findings, lessons, and deprecations
- `index.json` for machine lookup and `jq`-friendly queries

Root selection is local-first:
- default: nearest git repository's `.worklog/`
- outside git: current directory's `.worklog/`
- explicit global override: pass `--root ~/.claude/worklog`

## Using this skill in Claude Code

1. Copy `worklog/` into `~/.claude/skills/`.
2. Start Claude Code normally.
3. Ask Claude in natural language, for example:
   - "Record this session."
   - "Save a worklog for what we just did."
   - "Record this session as a mixed worklog."
   - "Save this debugging session."
   - "Search prior experiences about cache invalidation."
   - "Deprecate the passive_deletes experience."
4. Claude will infer the mode, draft a save-ready summary from context, and ask one compact confirmation before writing.

The default interaction is context-first and draft-first. `/worklog` should not start by asking you to fill title, status, tags, and sections. It should first show the inferred mode, evidence, title, summary bullets, and pending experience candidates. Use `/worklog edit` or `/worklog guided` only when you want detailed field-by-field control.

Use the helper scripts directly when you want automation, CI, bulk import, or manual reindexing.

- implementation decisions
- source-reading notes
- debugging pivots
- partial conclusions
- reusable experience that should survive the current chat

`worklog` gives Claude Code a consistent way to persist that information locally beside the project context. Add `.worklog/` to `.gitignore` for private logs, or commit selected logs intentionally when a project should carry its own history.

## Repository layout

```text
worklog/
├── worklog/                  # Claude skill source
├── examples/                 # Example JSON payloads for the scripts
├── tools/                    # Local validation and packaging helpers
└── .github/workflows/        # CI validation and packaging
```

## Installation

### Option 1: copy the skill directory

Copy `worklog/` into your Claude skills directory:

```bash
cp -R worklog ~/.claude/skills/
```

### Option 2: build a distributable `.skill` package

```bash
python3 tools/package_skill.py worklog ./dist
```

This creates `dist/worklog.skill`.

## 30-second quick start

```bash
python3 worklog/scripts/init_worklog.py
python3 worklog/scripts/finish_worklog.py --input examples/mixed-session.json
cat .worklog/INDEX.md
```

## Quick start

### 1. Initialize the local worklog store

```bash
python3 worklog/scripts/init_worklog.py
```

This creates:
- `.worklog/INDEX.md`
- `.worklog/EXPERIENCES.md`
- `.worklog/index.json`
- `.worklog/archive/`

### 2. Record one session from a JSON payload

```bash
python3 worklog/scripts/finish_worklog.py --input examples/mixed-session.json
```

Draft-first payloads can omit fields that Claude can safely default:

```bash
python3 worklog/scripts/finish_worklog.py --input examples/minimal-draft.json
```

### 3. Rebuild indexes after manual edits

```bash
python3 worklog/scripts/reindex_worklog.py
```

## Example input

You can pass JSON through stdin instead of a file:

```bash
python3 worklog/scripts/finish_worklog.py <<'EOF'
{
  "mode": "read",
  "project_path": "/path/to/project",
  "title": "Understand scheduler wake-up path",
  "started_at": "2026-05-12T09:00:00+08:00",
  "duration_minutes": 55,
  "status": "partial",
  "tags": ["read", "scheduler"],
  "read_type": "deep-dive",
  "target": "my-repo",
  "target_version": "main",
  "completion": 70,
  "sections": {
    "reading_goal": "Understand why delayed jobs wake late.",
    "entry_points": ["scheduler.py:120", "queue.py:44"],
    "mental_model": "Wake-up time is calculated once, then adjusted only after dequeue.",
    "key_findings": ["Clock skew is not the issue.", "Late wake-ups start after retry backoff."],
    "open_questions": ["Need to confirm whether backoff mutates in place."],
    "evidence": ["scheduler.py:120-178", "queue.py:44-80"],
    "follow_on_output": ["Add one experience if the backoff mutation is confirmed."]
  }
}
EOF
```

## Included examples

- `examples/dev-session.json`
- `examples/read-session.json`
- `examples/debug-session.json`
- `examples/mixed-session.json`
- `examples/minimal-draft.json`

## Privacy

This repository ships the skill source code only.

It does not upload or sync your project `.worklog/` data. If you want to share worklog history, do that intentionally through your own storage or version-control workflow.

## Development

Run a local smoke test:

```bash
python3 -m py_compile worklog/scripts/*.py tools/*.py
python3 worklog/scripts/init_worklog.py --root /tmp/worklog-test
python3 worklog/scripts/finish_worklog.py --root /tmp/worklog-test --input examples/mixed-session.json
python3 worklog/scripts/reindex_worklog.py --root /tmp/worklog-test
python3 tools/package_skill.py worklog ./dist
```

The GitHub Actions workflow validates the skill structure, compiles the scripts, runs an end-to-end smoke test, and packages the skill.

## License

MIT
