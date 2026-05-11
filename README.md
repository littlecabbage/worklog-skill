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

By default it writes three local artifacts under `~/.claude/worklog`:
- `INDEX.md` for human-readable session history
- `EXPERIENCES.md` for reusable findings, lessons, and deprecations
- `index.json` for machine lookup and `jq`-friendly queries

## Why use it

Most coding sessions produce more than code:
- implementation decisions
- source-reading notes
- debugging pivots
- partial conclusions
- reusable experience that should survive the current chat

`worklog` gives Claude Code a consistent way to persist that information locally without mixing it into your repository.

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
cat ~/.claude/worklog/INDEX.md
```

## Quick start

### 1. Initialize the local worklog store

```bash
python3 worklog/scripts/init_worklog.py
```

This creates:
- `~/.claude/worklog/INDEX.md`
- `~/.claude/worklog/EXPERIENCES.md`
- `~/.claude/worklog/index.json`
- `~/.claude/worklog/archive/`

### 2. Record one session from a JSON payload

```bash
python3 worklog/scripts/finish_worklog.py --input examples/mixed-session.json
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

## Privacy

This repository ships the skill source code only.

It does not upload or sync your real `~/.claude/worklog` data. If you want to share your personal worklog history, do that intentionally through your own storage or version-control workflow.

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
