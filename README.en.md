# worklog

[中文](README.md)

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
- `draft/<session_id>/events.jsonl` for structured events captured by the optional hook layer

Root selection is local-first:
- default: nearest git repository's `.worklog/`
- outside git: current directory's `.worklog/`
- explicit global override: pass `--root ~/.claude/worklog`

Output language follows the conversation: the main agent infers it at finalize time and writes `language` (`zh` or `en`) into the payload — mixed or unclear conversations default to `zh`. Only structural text (section headers, table column names, INDEX / EXPERIENCES preamble) is affected; bullet content and frontmatter keys stay as written.

## Using this skill in Claude Code

1. Copy `worklog/` into `~/.claude/skills/`.
2. From inside a project, run `python3 ~/.claude/skills/worklog/scripts/init_worklog.py` once. This creates the `.worklog/` skeleton, installs capture hooks, and patches `.gitignore`.
3. Start Claude Code normally. The hook layer begins recording structured events the moment your next session starts.
4. Ask Claude in natural language, for example:
   - "Record this session."
   - "Save a worklog for what we just did."
   - "Record this session as a mixed worklog."
   - "Save this debugging session."
   - "Search prior experiences about cache invalidation."
   - "Deprecate the passive_deletes experience."
5. Claude reads the captured events, file-history snapshots, and git state, drafts a save-ready summary, and asks one compact confirmation before writing.

The default interaction is context-first and draft-first. `/worklog` should not start by asking you to fill title, status, tags, and sections. It should first show the inferred mode, evidence, title, summary bullets, and pending experience candidates. Use `/worklog edit` or `/worklog guided` only when you want detailed field-by-field control.

Use the helper scripts directly when you want automation, CI, bulk import, or manual reindexing.

`worklog` is built for the kind of information that usually gets lost: implementation decisions, source-reading notes, debugging pivots, partial conclusions, and reusable experience that should survive the current chat. It persists those locally beside the project context. Add `.worklog/` to `.gitignore` for private logs, or commit selected logs intentionally when a project should carry its own history.

## Active capture (optional)

When `init_worklog.py` installs hooks, three Claude Code command hooks record structured events into `.worklog/draft/<session_id>/events.jsonl`:

- `UserPromptSubmit` — user prompt (truncated to 500 chars)
- `PostToolUse` — tool name + target file or command (truncated to 256 chars, redacted)
- `Stop` — last assistant reply excerpt (300 chars)

Sensitive file paths are redacted at capture time (`.env*`, `*secret*`, `*credential*`, `*token*`, `*.pem`, `*.key`, `id_rsa*`, anything under `.ssh/` or `.aws/`, `.netrc`).

The hook layer never calls an LLM, never blocks the main conversation, and silently exits on any failure. The drafts are per-session-id, so multiple concurrent sessions in the same project never interfere. To temporarily disable capture, set `WORKLOG_HOOK_ACTIVE=1`.

To remove the capture layer entirely:

```bash
python3 worklog/scripts/init_worklog.py --uninstall
```

This removes the hooks and the `.gitignore` entry but preserves all `.worklog/` data.

## Repository layout

```text
worklog/
├── worklog/                  # Claude skill source
│   ├── SKILL.md
│   ├── scripts/              # init / capture_hook / hooks_install / finish / reindex / search
│   ├── references/           # worklog format reference
│   └── tests/                # unittest suite (52 tests)
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
python3 worklog/scripts/init_worklog.py            # skeleton + hooks + .gitignore
python3 worklog/scripts/finish_worklog.py <<EOF
{"mode":"mixed","title":"Quick smoke test","language":"en","sections":{"timeline":["init OK"],"outputs":{"code":"","knowledge":"","remaining":""},"experience_candidates":[]},"original_goal":"smoke","final_outcome":"OK","primary_type":"dev"}
EOF
cat .worklog/INDEX.md
```

## Quick start

### 1. Initialize the worklog in your project

```bash
python3 worklog/scripts/init_worklog.py
```

By default this does three things:
- creates `.worklog/INDEX.md`, `EXPERIENCES.md`, `index.json`, and `archive/`
- installs capture hooks at `~/.claude/hooks/worklog-capture.sh` and registers them in `.claude/settings.local.json`
- appends `/.worklog/draft/` to `.gitignore`

Useful flags:
- `--dry-run` — print the plan without writing
- `--skip-hooks` — only create the skeleton
- `--skip-gitignore` — leave `.gitignore` alone
- `--global` — register hooks in `~/.claude/settings.json` instead of the project
- `--uninstall` — reverse the install, preserving `.worklog/` data

### 2. Manage capture hooks separately

When you only need to add or remove the capture layer:

```bash
python3 worklog/scripts/hooks_install.py             # install
python3 worklog/scripts/hooks_install.py --uninstall # remove
```

Same `--project` / `--global` / `--dry-run` flags as `init_worklog.py`.

### 3. Record one session from JSON

See [worklog/references/worklog-format.md](worklog/references/worklog-format.md) for field definitions; pipe a payload via stdin or `--input`:

```bash
python3 worklog/scripts/finish_worklog.py <<'EOF'
{
  "mode": "dev",
  "language": "en",
  "title": "Implement soft delete for users",
  "started_at": "2026-05-12T09:30:00+08:00",
  "duration_minutes": 90,
  "status": "completed",
  "tags": ["dev", "backend"],
  "sections": {
    "goal": "Add soft delete support for users.",
    "completed": ["Added deleted_at column.", "Updated service queries."],
    "key_decisions": [{"decision": "Nullable timestamp", "why": "preserves deletion time"}]
  }
}
EOF
```

Draft-first payloads can omit fields that the script can safely default before validation.

### 4. Rebuild indexes after manual edits

```bash
python3 worklog/scripts/reindex_worklog.py
```

## Example input

You can pass JSON through stdin. See [worklog/references/worklog-format.md](worklog/references/worklog-format.md) for the per-mode field schema:

```bash
python3 worklog/scripts/finish_worklog.py <<'EOF'
{
  "mode": "read",
  "language": "en",
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

## Privacy

This repository ships the skill source code only. It does not upload or sync your project `.worklog/` data.

The capture hook layer records file *paths* and tool names, never tool output content. Sensitive file paths are redacted at capture time. User prompts are recorded literally (truncated, but not redacted) — if your prompts can contain secrets, disable capture before pasting them or run `init_worklog.py --uninstall`.

If you want to share worklog history, do that intentionally through your own storage or version-control workflow.

## Development

Run the unittest suite:

```bash
python3 -m unittest discover worklog/tests
```

Local smoke test:

```bash
python3 -m py_compile worklog/scripts/*.py tools/*.py
python3 worklog/scripts/init_worklog.py --root /tmp/worklog-test --skip-hooks
python3 worklog/scripts/reindex_worklog.py --root /tmp/worklog-test
python3 tools/package_skill.py worklog ./dist
```

The GitHub Actions workflow validates the skill structure, compiles the scripts, runs an end-to-end smoke test, and packages the skill.

## License

MIT
