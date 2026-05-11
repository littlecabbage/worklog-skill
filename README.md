# worklog

A Claude Code skill for recording session work logs and maintaining a reusable experience library.

The skill supports four session modes:
- `dev`
- `read`
- `debug-session`
- `mixed`

It writes three local artifacts under `~/.claude/worklog` by default:
- `INDEX.md` for human-readable session history
- `EXPERIENCES.md` for reusable findings and deprecations
- `index.json` for machine lookup and `jq` queries

## Repository layout

```text
worklog/
├── worklog/                  # Claude skill source
├── examples/                 # Example JSON payloads for scripts
└── .github/workflows/        # Validation and packaging workflow
```

## Install

### Option 1: copy the skill directory

Copy `worklog/` into your Claude skills directory:

```bash
cp -R worklog ~/.claude/skills/
```

### Option 2: package the skill

Package the skill and distribute `worklog.skill`:

```bash
python3 tools/package_skill.py worklog ./dist
```

## Initialize the local worklog store

```bash
python3 worklog/scripts/init_worklog.py
```

This creates `~/.claude/worklog/` with:
- `INDEX.md`
- `EXPERIENCES.md`
- `index.json`
- `archive/`

## Record one session

Pass a JSON payload to `finish_worklog.py`.

```bash
python3 worklog/scripts/finish_worklog.py --input examples/mixed-session.json
```

Or stream JSON on stdin:

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

## Rebuild indexes from markdown

```bash
python3 worklog/scripts/reindex_worklog.py
```

Use this after manual edits to `EXPERIENCES.md` or if `index.json` drifts.

## Examples

- `examples/dev-session.json`
- `examples/read-session.json`
- `examples/debug-session.json`
- `examples/mixed-session.json`

## Privacy

This repository shares the skill source code only.

It does not upload or sync your real `~/.claude/worklog` data. Do not commit your personal worklog directory unless you intentionally want to publish it.

## Development

Smoke-test the scripts locally:

```bash
python3 -m py_compile worklog/scripts/*.py
python3 worklog/scripts/init_worklog.py --root /tmp/worklog-test
python3 worklog/scripts/finish_worklog.py --root /tmp/worklog-test --input examples/mixed-session.json
python3 worklog/scripts/reindex_worklog.py --root /tmp/worklog-test
```

The GitHub Actions workflow validates the skill structure, compiles scripts, and runs an end-to-end smoke test.

## License

MIT
