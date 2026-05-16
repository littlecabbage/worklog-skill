# worklog

[English](README.en.md)

一个可共享的 Claude Code skill，用于把单次工作会话整理成可检索的工作日志，并沉淀可复用的工程经验。

`worklog` 不只记录"做了什么"，还会记录：
- 学到了什么
- 排除了什么
- 哪些经验值得之后再次引用

## 它做什么

这个 skill 支持四种会话模式：
- `dev`
- `read`
- `debug-session`
- `mixed`

默认会把内容写到当前仓库的 `.worklog/` 目录：
- `INDEX.md`：人类可读的会话索引
- `EXPERIENCES.md`：可复用的经验、教训和过期条目
- `index.json`：给机器检索和 `jq` 查询用的索引
- `draft/<session_id>/events.jsonl`：可选的 hook 采集层落地的结构化事件流

root 选择遵循 local-first：
- 默认：最近的 git 仓库 `.worklog/`
- 不在 git 仓库中：当前目录 `.worklog/`
- 显式全局覆盖：传入 `--root ~/.claude/worklog`

输出语言会自动跟随对话：主 agent 在 finalize 时判定语言并填入 payload 的 `language` 字段（`zh` 或 `en`），中英混合默认 `zh`。只影响 section 标题、表格列名、INDEX/EXPERIENCES 顶部这类结构性文本——bullet 内容和 frontmatter key 不会被翻译。

## 在 Claude Code 中使用

1. 把 `worklog/` 复制到 `~/.claude/skills/`。
2. 进到项目目录，执行一次 `python3 ~/.claude/skills/worklog/scripts/init_worklog.py`。这会创建 `.worklog/` 骨架、安装采集 hook、并给 `.gitignore` 加一行。
3. 正常启动 Claude Code。下一次会话开始时，hook 层会立即开始记录结构化事件。
4. 直接对 Claude 说，例如：
   - "记录这次会话。"
   - "把刚才做的事保存成 worklog。"
   - "把这次会话记录成 mixed worklog。"
   - "保存这次 debug 会话。"
   - "查一下以前关于 cache invalidation 的经验。"
   - "把 passive_deletes 那条经验标记过期。"
5. Claude 会综合采集事件、file-history 快照和 git 状态，先生成草稿，再用一次极简确认后写入本地 worklog。

默认交互是 context-first / draft-first。`/worklog` 不应该一开始就要求你填写标题、状态、标签和 sections，而应该先展示推断的 mode、证据、标题、摘要要点和待确认的经验候选。只有当你明确想逐项精修时，才使用 `/worklog edit` 或 `/worklog guided`。

需要自动化、CI、批量导入或手动重建索引时，再直接运行脚本。

`worklog` 专门面向那种"容易丢失"的信息：实现决策、阅读源码笔记、调试过程中的转折点、还没做完的结论，以及值得长期保留的经验。它把这些东西本地化地放在项目上下文旁边。私有日志可以把 `.worklog/` 加入 `.gitignore`；如果某个项目需要携带历史，也可以有意识地提交选中的日志。

## 主动采集（可选）

`init_worklog.py` 会安装三个 Claude Code command hook，把结构化事件写到 `.worklog/draft/<session_id>/events.jsonl`：

- `UserPromptSubmit` — 用户 prompt（截断到 500 字符）
- `PostToolUse` — 工具名 + 目标文件/命令（截断到 256 字符，路径脱敏）
- `Stop` — assistant 最后一条回复摘要（300 字符）

敏感文件路径在采集时就脱敏（`.env*`、`*secret*`、`*credential*`、`*token*`、`*.pem`、`*.key`、`id_rsa*`、`.ssh/` 和 `.aws/` 下的任何文件、`.netrc`）。

采集层从不调用 LLM、从不阻塞主对话，任何失败都静默退出。Draft 按 session-id 物理隔离，同一项目里多个并发会话互不干扰。需要临时禁用采集，设环境变量 `WORKLOG_HOOK_ACTIVE=1` 即可短路。

要彻底移除采集层：

```bash
python3 worklog/scripts/init_worklog.py --uninstall
```

这会移除 hook 注册和 `.gitignore` 条目，但**保留**所有 `.worklog/` 数据。

## 仓库结构

```text
worklog/
├── worklog/                  # Claude skill 源码
│   ├── SKILL.md
│   ├── scripts/              # init / capture_hook / hooks_install / finish / reindex / search
│   ├── references/           # worklog 格式参考
│   └── tests/                # unittest 套件（52 个测试）
├── tools/                    # 本地校验和打包工具
└── .github/workflows/        # CI 校验和打包
```

## 安装

### 方式一：复制 skill 目录

把 `worklog/` 复制到 Claude skills 目录：

```bash
cp -R worklog ~/.claude/skills/
```

### 方式二：打包成 `.skill`

```bash
python3 tools/package_skill.py worklog ./dist
```

会生成 `dist/worklog.skill`。

## 30 秒快速开始

```bash
python3 worklog/scripts/init_worklog.py            # 骨架 + hooks + .gitignore
python3 worklog/scripts/finish_worklog.py <<EOF
{"mode":"mixed","title":"Quick smoke test","language":"zh","sections":{"timeline":["init OK"],"outputs":{"code":"","knowledge":"","remaining":""},"experience_candidates":[]},"original_goal":"smoke","final_outcome":"OK","primary_type":"dev"}
EOF
cat .worklog/INDEX.md
```

## 快速开始

### 1. 在项目里初始化 worklog

```bash
python3 worklog/scripts/init_worklog.py
```

默认做三件事：
- 创建 `.worklog/INDEX.md`、`EXPERIENCES.md`、`index.json`、`archive/`
- 在 `~/.claude/hooks/worklog-capture.sh` 安装 shim，并在 `.claude/settings.local.json` 里注册三个 hook
- 给 `.gitignore` 追加 `/.worklog/draft/`

常用参数：
- `--dry-run` — 只打印计划，不写
- `--skip-hooks` — 只建骨架，不装 hook
- `--skip-gitignore` — 不动 `.gitignore`
- `--global` — 把 hook 注册到 `~/.claude/settings.json` 而不是项目级
- `--uninstall` — 反向卸载，保留 `.worklog/` 数据

### 2. 单独管理采集 hook

只想增删采集层（不动 `.worklog/` 骨架）：

```bash
python3 worklog/scripts/hooks_install.py             # 安装
python3 worklog/scripts/hooks_install.py --uninstall # 移除
```

支持的 `--project` / `--global` / `--dry-run` 参数和 `init_worklog.py` 一致。

### 3. 用 JSON 写入一条会话

参考 [worklog/references/worklog-format.zh.md](worklog/references/worklog-format.zh.md) 的字段定义，自己拼一份 JSON 后通过 stdin 或 `--input` 传入：

```bash
python3 worklog/scripts/finish_worklog.py <<'EOF'
{
  "mode": "dev",
  "language": "zh",
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

draft-first 的 JSON 可以省略 Claude 能安全补齐的字段——`finish_worklog.py` 会先补默认值再校验。

### 4. 手动修改后重建索引

```bash
python3 worklog/scripts/reindex_worklog.py
```

## 示例输入

也可以直接从 stdin 传 JSON。各 mode 的字段定义见 [worklog/references/worklog-format.zh.md](worklog/references/worklog-format.zh.md)：

```bash
python3 worklog/scripts/finish_worklog.py <<'EOF'
{
  "mode": "read",
  "language": "zh",
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

## 隐私

这个仓库只发布 skill 源码，不会上传或同步你的项目 `.worklog/` 数据。

采集 hook 只记录文件**路径**和工具名，不记录工具输出内容。敏感文件路径在采集时就脱敏。用户 prompt 会被原文记下（只截断不脱敏）——如果你的 prompt 里可能包含密钥，记得粘贴前先禁用采集，或者跑 `init_worklog.py --uninstall`。

如果你想分享 worklog 历史，请通过自己的存储或版本控制流程有意识地发布。

## 开发

跑 unittest 套件：

```bash
python3 -m unittest discover worklog/tests
```

本地烟雾测试：

```bash
python3 -m py_compile worklog/scripts/*.py tools/*.py
python3 worklog/scripts/init_worklog.py --root /tmp/worklog-test --skip-hooks
python3 worklog/scripts/reindex_worklog.py --root /tmp/worklog-test
python3 tools/package_skill.py worklog ./dist
```

GitHub Actions 会校验 skill 结构、编译脚本、跑端到端烟雾测试，并打包 skill。

## 许可证

MIT
