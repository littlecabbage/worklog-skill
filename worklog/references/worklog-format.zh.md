# Worklog 格式参考（中文版）

## 文件布局

```text
<project-root>/.worklog/
├── INDEX.md
├── EXPERIENCES.md
├── index.json
├── YYYY-MM-DD/
│   └── <task-slug>.md
└── archive/
```

默认 root 是项目本地：最近 git 仓库的 `.worklog/`；如果不在 git 仓库中，则使用当前目录的 `.worklog/`。只有明确传入 `--root ~/.claude/worklog` 时，才使用全局的本机 store；显式全局 root 会保留 `<project-slug>/YYYY-MM-DD/<task-slug>.md` 分组。

## 通用 worklog frontmatter

必填：
- `id`
- `mode`
- `project`
- `project_path`
- `title`
- `started_at`
- `duration_minutes`
- `status`
- `tags`
- `language`（`en` | `zh`）—— 由主 agent 根据对话语言判定；只影响渲染时的结构性文本（section 标题、表格列名等），不影响内容

draft-first 的脚本输入可以省略大部分字段。`finish_worklog.py` 会在校验前补安全默认值：
- `mode`：`mixed`
- `project_path`：当前工作目录
- `title`：`Worklog draft`
- `started_at`：当前本地时间
- `duration_minutes`：`0`
- `status`：`partial`
- `tags`：按 mode 派生
- `language`：`zh`（与脚本层 `DEFAULT_LANGUAGE` 一致）

可选草稿元数据：
- `mode_confidence`（`high` | `medium` | `low`）
- `mode_evidence[]`
- `draft_confirmed`

## 各模式字段

### `dev`
- `branch`
- `commits[]`
- `files_changed[]`
- `loc.added`
- `loc.deleted`
- `pr_url`

### `read`
- `read_type`（`survey` | `deep-dive` | `hunt` | `compare`）
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

字段未知时，优先生成一个结构完整的草稿并使用默认值，不要把用户阻塞在填表流程里。只有 mode 低置信度或准备正式写入经验库时，才做有针对性的追问。

## 正文结构

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

## EXPERIENCES.md 规则

- 新条目追加到最新日期块顶部。
- 标记过期时保留原文。
- 过期/错误内容用 `~~...~~`。
- 保留回到原 worklog 的链接。
- 每条经验块上方都要有 YAML 元数据注释。

### 元数据注释

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

顶层键：
- `version`
- `updated_at`
- `experiences[]`
- `worklogs[]`
- `snippets[]`
- `debug_sessions[]`
- `stats`

### 经验字段
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

## jq 模式

```bash
jq '.experiences[] | select(.status=="active" and (.tags|index("sqlalchemy"))) | {id,title,location}' .worklog/index.json
jq '.worklogs[] | select(.project=="my-project") | {id,date,mode,title,file}' .worklog/index.json
jq '.experiences[] | select(.confidence=="high") | {id,title,location}' .worklog/index.json
```

## 检索规则

先用 `jq` 缩小候选，再只读取对应 markdown 的锚点或行范围。
