# Worklog format reference

## File layout

```text
<project-root>/.worklog/
├── INDEX.md
├── EXPERIENCES.md
├── index.json
├── YYYY-MM-DD/
│   └── <task-slug>.md
└── archive/
```

The default root is project-local: the nearest git repository's `.worklog/`, or the current directory's `.worklog/` when no git root is found. Pass `--root ~/.claude/worklog` to intentionally use a global machine-local store; explicit global roots preserve `<project-slug>/YYYY-MM-DD/<task-slug>.md` grouping.

## Common worklog frontmatter

Required:
- `id`
- `mode`
- `project`
- `project_path`
- `title`
- `started_at`
- `duration_minutes`
- `status`
- `tags`

Draft-first script inputs may omit most of these fields. `finish_worklog.py` fills safe defaults before validation:
- `mode`: `mixed`
- `project_path`: current working directory
- `title`: `Worklog draft`
- `started_at`: current local time
- `duration_minutes`: `0`
- `status`: `partial`
- `tags`: a mode-derived default

Optional draft metadata:
- `mode_confidence` (`high` | `medium` | `low`)
- `mode_evidence[]`
- `draft_confirmed`

## Mode-specific fields

### `dev`
- `branch`
- `commits[]`
- `files_changed[]`
- `loc.added`
- `loc.deleted`
- `pr_url`

### `read`
- `read_type` (`survey` | `deep-dive` | `hunt` | `compare`)
- `target`
- `target_version`
- `completion`

### `debug-session`
- `debug_id`
- `session_number`
- `linked_debug_doc`

### `mixed`
- `original_goal`
- `final_outcome`
- `involved[]`
- `primary_type`

When fields are unknown, prefer a coherent draft with defaults over blocking the user with a form. Ask a targeted follow-up only for low-confidence mode selection or before writing confirmed experiences.

## Body sections

### `dev`
- 目标
- 完成情况
- 关键决策
- 学到 / 经验候选
- 遗留 TODO
- 参考

### `read`
- 阅读目标
- 入口与路径
- 一句话心智模型
- 关键发现
- 未解 / 下次继续
- 引用证据
- 衍生产出

### `debug-session`
- 历次会话
- 本次进展
- 当前状态
- 下次会话从这里继续
- 假设池摘要
- 经验候选

### `mixed`
- 主线时间线
- 关键决策
- 产出
- 经验候选

## EXPERIENCES.md rules

- Prepend new entries under the newest date block.
- Keep the original wording when deprecating.
- Use `~~...~~` for stale or wrong content.
- Keep source links to the original worklog.
- Put a YAML metadata comment above every experience block.

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

## index.json schema

Top-level keys:
- `version`
- `updated_at`
- `experiences[]`
- `worklogs[]`
- `snippets[]`
- `debug_sessions[]`
- `stats`

### Experience fields
- `id`
- `title`
- `summary`
- `tags[]`
- `search_keywords[]`
- `project`
- `confidence`
- `status`
- `date`
- `location.file`
- `location.anchor`
- `location.line`
- `source_worklog_id`
- `verified_against`
- `last_verified_at`
- `supersedes`
- `superseded_by`
- `ref_count`
- `pinned`
- `deprecated_at`
- `deprecated_reason`

## jq patterns

```bash
jq '.experiences[] | select(.status=="active" and (.tags|index("sqlalchemy"))) | {id,title,location}' .worklog/index.json
jq '.worklogs[] | select(.project=="my-project") | {id,date,mode,title,file}' .worklog/index.json
jq '.experiences[] | select(.confidence=="high") | {id,title,location}' .worklog/index.json
```

## Retrieval rule

Use `jq` to shortlist candidates first, then read only the matching markdown anchor or line range.
