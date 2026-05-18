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

## 三层契约

设计上区分三层，每层职责不同：

| 层 | 谁产生 | 用途 |
|---|---|---|
| **input payload** | LLM 生成的 JSON | 调用 `finish_worklog.py` 时的输入 |
| **frontmatter** | 脚本写入 `.md` 顶部 | 长期归档；`reindex_worklog.py` 重建索引时回读 |
| **index entry** | 脚本写入 `index.json` | `jq` 检索的机器层 |

只有显式列出的字段会进入 frontmatter / index。其它字段会被静默丢弃（带 stderr warning），不要依赖未声明的字段被持久化。

## Input payload（LLM 生成）

```json
{
  "mode": "dev",
  "title": "把 worklog schema 改成 body-first",
  "status": "completed",
  "started_at": "2026-05-18T10:00:00+08:00",
  "duration_minutes": 30,
  "tags": ["worklog", "schema"],
  "language": "zh",
  "summary": "把 sections dict 改成自由 markdown body，并扩大 index 检索字段。",
  "search_keywords": ["body-first", "schema 简化"],
  "body": "## 目标\n\n......\n\n## 完成\n\n- ...",
  "experiences": [],
  "meta": {
    "branch": "main",
    "pr_url": "https://example.com/pr/1"
  }
}
```

### 必填字段
- `mode`：`dev` / `read` / `debug-session` / `mixed`
- `title`：人类可读的一行标题
- `summary`：1-2 句的可检索摘要，会进 `index.json` 的 worklog 条目
- `body`：完整的 markdown 正文。**不要以 `---` 开头**，那是 frontmatter 围栏的字符
- `status`：`completed` / `partial` / `paused` / `blocked` / `abandoned`
- `started_at`：ISO 8601 时间戳
- `duration_minutes`：非负整数

### 可选字段
- `tags[]`：缺省按 mode 派生
- `language`：`en` / `zh`。**省略时脚本根据 body 中 CJK 字符占比自动推断**（>30% → `zh`，否则 `en`），失败时回退默认 zh
- `search_keywords[]`：补充检索词，会进 `index.json` 的 worklog 条目
- `experiences[]`：见下文经验库章节
- `meta`：模式相关字段（见下）

### `meta` 容忍嵌套与 flat
脚本同时接受这两种写法：

```json
"meta": {"branch": "main", "pr_url": "..."}
```

```json
"meta": {"dev": {"branch": "main", "pr_url": "..."}}
```

未声明的 key（无论顶层还是嵌套）都会被丢弃并 warning。落盘时永远是 flat。

### 模式相关字段（顶层或 meta.<mode>.* 都可）
- **dev**：`branch` / `commits[]` / `files_changed[]` / `loc.{added,deleted}` / `pr_url`
- **read**：`read_type` (`survey`/`deep-dive`/`hunt`/`compare`) / `target` / `target_version` / `completion` (0-100)
- **debug-session**：`debug_id` / `session_number` / `linked_debug_doc`
- **mixed**：`original_goal` / `final_outcome` / `involved[]` / `primary_type` (`dev`/`read`/`debug`)

### 不再持久化的字段
以下交互期信号**不再写入 frontmatter**：
- `mode_confidence` / `mode_evidence`：用于 confirmation UI 给用户看，不落盘
- `draft_confirmed`：草稿确认是工作流义务（未确认就不调脚本），不靠落盘字段背书

### Legacy `sections` payload
已废弃并移除。脚本遇到含 `sections` 的输入直接报错，引导迁移到 `body`。

## Body 写作建议

`body` 是自由 markdown，脚本不解析其中结构。下面是各模式的常用章节，**仅供参考，不强制**。模型可根据上下文增删合并；只要 `summary` 写好，检索不依赖正文结构。

### `dev`
- 目标
- 完成
- 关键决策
- 经验候选
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
- 历次会话回顾
- 本次进展
- 当前状态
- 下次从这里继续
- 假设与证据
- 经验候选

### `mixed`
- 主线时间线
- 关键决策
- 产出（代码 / 知识 / 遗留）
- 经验候选

## Frontmatter（脚本生成）

通用：`id` `mode` `project` `project_path` `title` `started_at` `duration_minutes` `status` `tags` `language` `summary` `search_keywords` `produced_experience_ids`

按 mode 追加：见上文"模式相关字段"；脚本会从 payload 的顶层（或 flat 化后的 meta）取对应字段。

## index.json schema

顶层键：`version` `updated_at` `experiences[]` `worklogs[]` `snippets[]` `debug_sessions[]` `stats`

### Worklog 条目字段
- 通用：`id` `date` `project` `mode` `title` `summary` `search_keywords[]` `tags[]` `duration_minutes` `status` `file` `language` `produced_experience_ids[]`
- debug-session：`debug_id` `session_number` `linked_debug_doc`
- dev：`commits[]`（hash 数组）`branch` `pr_url`
- read：`read_type` `target` `target_version` `completion`
- mixed：`primary_type` `involved[]`

### Experience 条目字段
- `id` `title` `summary` `tags[]` `search_keywords[]` `project` `confidence` `status` `date`
- `location.{file,anchor,line}` `source_worklog_id`
- `verified_against` `last_verified_at` `supersedes` `superseded_by`
- `ref_count` `pinned` `deprecated_at` `deprecated_reason`

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

## jq 模式

```bash
jq '.experiences[] | select(.status=="active" and (.tags|index("sqlalchemy"))) | {id,title,location}' .worklog/index.json
jq '.worklogs[] | select(.project=="my-project") | {id,date,mode,title,summary,file}' .worklog/index.json
jq '.worklogs[] | select(.summary | test("body-first"; "i")) | {id,title}' .worklog/index.json
jq '.experiences[] | select(.confidence=="high") | {id,title,location}' .worklog/index.json
```

## 检索规则

先用 `jq` 在 `index.json` 缩小候选（结合 `summary` / `search_keywords` / `tags` / `mode` / `target`），再只读取对应 markdown 的锚点或行范围。
