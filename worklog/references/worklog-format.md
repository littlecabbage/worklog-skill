# Worklog format reference

## Layout

```text
<project-root>/.worklog/
├── INDEX.md
├── EXPERIENCES.md
├── index.json
├── YYYY-MM-DD/
│   └── <task-slug>.md
└── archive/
```

The default root is project-local: the nearest git repository's `.worklog/`, or the current directory's `.worklog/` if not in a git repo. Pass `--root ~/.claude/worklog` only when a global machine-local store is intentionally desired; explicit global roots keep the `<project-slug>/YYYY-MM-DD/<task-slug>.md` grouping.

## Three-layer contract

| Layer | Produced by | Purpose |
|---|---|---|
| **input payload** | LLM-generated JSON | Argument to `finish_worklog.py` |
| **frontmatter** | Script writes to top of `.md` | Long-term archive; replayed by `reindex_worklog.py` |
| **index entry** | Script writes to `index.json` | Machine layer for `jq` retrieval |

Only fields explicitly listed below land in frontmatter / index. Unknown fields are silently dropped (with a stderr warning); do not rely on undeclared fields to be persisted.

## Input payload (LLM-authored)

```json
{
  "mode": "dev",
  "title": "Switch worklog schema to body-first",
  "status": "completed",
  "started_at": "2026-05-18T10:00:00+08:00",
  "duration_minutes": 30,
  "tags": ["worklog", "schema"],
  "language": "en",
  "summary": "Replace the sections dict with free-form markdown body and broaden index search fields.",
  "search_keywords": ["body-first", "schema cleanup"],
  "body": "## Goal\n\n...\n\n## Done\n\n- ...",
  "experiences": [],
  "meta": {
    "branch": "main",
    "pr_url": "https://example.com/pr/1"
  }
}
```

### Required fields
- `mode`: one of `dev` / `read` / `debug-session` / `mixed`
- `title`: human-readable one-line title
- `summary`: 1-2 sentence searchable abstract; lands in the worklog entry of `index.json`
- `body`: full markdown content. **Must not begin with `---`** (that's the frontmatter fence)
- `status`: `completed` / `partial` / `paused` / `blocked` / `abandoned`
- `started_at`: ISO 8601 timestamp
- `duration_minutes`: non-negative integer

### Optional fields
- `tags[]`: defaults to a per-mode tag if omitted
- `language`: `en` / `zh`. **Auto-detected from CJK ratio in body when omitted** (>30% → `zh`, otherwise `en`); falls back to `zh` if detection fails
- `search_keywords[]`: extra retrieval terms; lands in the worklog entry of `index.json`
- `experiences[]`: see Experience library below
- `meta`: mode-specific fields (see below)

### `meta` accepts both nested and flat
The script accepts either form:

```json
"meta": {"branch": "main", "pr_url": "..."}
```

```json
"meta": {"dev": {"branch": "main", "pr_url": "..."}}
```

Unknown keys (top-level or nested) are dropped with a warning. Persisted form is always flat.

### Mode-specific fields (top-level or `meta.<mode>.*`)
- **dev**: `branch` / `commits[]` / `files_changed[]` / `loc.{added,deleted}` / `pr_url`
- **read**: `read_type` (`survey`/`deep-dive`/`hunt`/`compare`) / `target` / `target_version` / `completion` (0-100)
- **debug-session**: `debug_id` / `session_number` / `linked_debug_doc`
- **mixed**: `original_goal` / `final_outcome` / `involved[]` / `primary_type` (`dev`/`read`/`debug`)

### Fields no longer persisted
The following draft-time signals are **not written to frontmatter**:
- `mode_confidence` / `mode_evidence`: shown to the user in the confirmation UI, not on disk
- `draft_confirmed`: confirmation is a workflow obligation (don't call the script before the user confirms), not a stored flag

### Legacy `sections` payload
Removed. The script now exits with an error if `sections` appears in the payload; migrate to `body`.

## Body writing guide

`body` is free-form markdown — the script does not parse it. Below are common section sets per mode, **suggestion only, not enforced**. Add, drop, or merge sections as the context demands; retrieval relies on `summary` + `search_keywords` + `tags`, not body structure.

### `dev`
- Goal
- Done
- Key decisions
- Experience candidates
- Remaining TODOs
- References

### `read`
- Reading goal
- Entry points and path
- One-sentence mental model
- Key findings
- Open questions / where to resume
- Evidence
- Follow-on output

### `debug-session`
- Prior sessions
- Progress this session
- Current status
- Resume here next time
- Hypotheses and evidence
- Experience candidates

### `mixed`
- Timeline
- Key decisions
- Outputs (code / knowledge / remaining)
- Experience candidates

## Frontmatter (script-generated)

Common: `id` `mode` `project` `project_path` `title` `started_at` `duration_minutes` `status` `tags` `language` `summary` `search_keywords` `produced_experience_ids`

Mode-specific: see "Mode-specific fields" above; the script sources them from the payload top level (or flattened `meta`).

## index.json schema

Top-level keys: `version` `updated_at` `experiences[]` `worklogs[]` `snippets[]` `debug_sessions[]` `stats`

### Worklog entry fields
- Common: `id` `date` `project` `mode` `title` `summary` `search_keywords[]` `tags[]` `duration_minutes` `status` `file` `language` `produced_experience_ids[]`
- debug-session: `debug_id` `session_number` `linked_debug_doc`
- dev: `commits[]` (hash array) `branch` `pr_url`
- read: `read_type` `target` `target_version` `completion`
- mixed: `primary_type` `involved[]`

### Experience entry fields
- `id` `title` `summary` `tags[]` `search_keywords[]` `project` `confidence` `status` `date`
- `location.{file,anchor,line}` `source_worklog_id`
- `verified_against` `last_verified_at` `supersedes` `superseded_by`
- `ref_count` `pinned` `deprecated_at` `deprecated_reason`

## EXPERIENCES.md rules

- Append new entries to the top of the latest date block.
- Keep the original wording when deprecating.
- Mark stale or wrong content with `~~...~~`.
- Preserve a link back to the source worklog.
- Each experience block must have a YAML metadata comment above it.

### Metadata comment

```html
<!-- exp-meta:
id: exp-YYYY-MM-DD-NNN
tags: [tag1, tag2]
project: my-project
confidence: high
status: active
verified_against: version-or-commit
last_verified_at: YYYY-MM-DD
supersedes: null
superseded_by: null
pinned: false
deprecated_at: null
deprecated_reason: null
-->
```

## jq patterns

```bash
jq '.experiences[] | select(.status=="active" and (.tags|index("sqlalchemy"))) | {id,title,location}' .worklog/index.json
jq '.worklogs[] | select(.project=="my-project") | {id,date,mode,title,summary,file}' .worklog/index.json
jq '.worklogs[] | select(.summary | test("body-first"; "i")) | {id,title}' .worklog/index.json
jq '.experiences[] | select(.confidence=="high") | {id,title,location}' .worklog/index.json
```

## Retrieval rules

Shortlist with `jq` on `index.json` first (combine `summary` / `search_keywords` / `tags` / `mode` / `target`), then read only the matching markdown anchor or line range.
