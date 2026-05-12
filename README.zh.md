# worklog

一个可共享的 Claude Code skill，用于把单次工作会话整理成可检索的工作日志，并沉淀可复用的工程经验。

`worklog` 不只记录“做了什么”，还会记录：
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

root 选择遵循 local-first：
- 默认：最近的 git 仓库 `.worklog/`
- 不在 git 仓库中：当前目录 `.worklog/`
- 显式全局覆盖：传入 `--root ~/.claude/worklog`

## 在 Claude Code 中使用

1. 把 `worklog/` 复制到 `~/.claude/skills/`。
2. 正常启动 Claude Code。
3. 直接对 Claude 说，例如：
   - “记录这次会话。”
   - “把刚才做的事保存成 worklog。”
   - “把这次会话记录成 mixed worklog。”
   - “保存这次 debug 会话。”
   - “查一下以前关于 cache invalidation 的经验。”
   - “把 passive_deletes 那条经验标记过期。”
4. Claude 会先从上下文推断模式、生成可保存的草稿，再用一次极简确认后写入本地 worklog。

默认交互是 context-first / draft-first。`/worklog` 不应该一开始就要求你填写标题、状态、标签和 sections，而应该先展示推断的 mode、证据、标题、摘要要点和待确认的经验候选。只有当你明确想逐项精修时，才使用 `/worklog edit` 或 `/worklog guided`。

需要自动化、CI、批量导入或手动重建索引时，再直接运行脚本。

- 关键决策
- 阅读源码笔记
- 调试过程中的转折点
- 还没做完的结论
- 值得长期保留的经验

`worklog` 让 Claude Code 用统一方式把这些内容保存在项目上下文旁边。私有日志可以把 `.worklog/` 加入 `.gitignore`；如果某个项目需要携带历史，也可以有意识地提交选中的日志。

## 仓库结构

```text
worklog/
├── worklog/                  # Claude skill 源码
├── examples/                 # 脚本输入示例
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
python3 worklog/scripts/init_worklog.py
python3 worklog/scripts/finish_worklog.py --input examples/mixed-session.json
cat .worklog/INDEX.md
```

## 快速开始

### 1. 初始化本地 worklog 存储

```bash
python3 worklog/scripts/init_worklog.py
```

会创建：
- `.worklog/INDEX.md`
- `.worklog/EXPERIENCES.md`
- `.worklog/index.json`
- `.worklog/archive/`

### 2. 记录一次会话

```bash
python3 worklog/scripts/finish_worklog.py --input examples/mixed-session.json
```

draft-first 的 JSON 可以省略 Claude 能安全补齐的字段：

```bash
python3 worklog/scripts/finish_worklog.py --input examples/minimal-draft.json
```

### 3. 手动修改后重建索引

```bash
python3 worklog/scripts/reindex_worklog.py
```

## 示例输入

也可以直接从 stdin 传 JSON：

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

## 包含的示例

- `examples/dev-session.json`
- `examples/read-session.json`
- `examples/debug-session.json`
- `examples/mixed-session.json`
- `examples/minimal-draft.json`

## 隐私

这个仓库只发布 skill 源码，不会上传或同步你的项目 `.worklog/` 数据。

如果你想分享 worklog 历史，请通过自己的存储或版本控制流程有意识地发布。

## 开发

本地烟雾测试：

```bash
python3 -m py_compile worklog/scripts/*.py tools/*.py
python3 worklog/scripts/init_worklog.py --root /tmp/worklog-test
python3 worklog/scripts/finish_worklog.py --root /tmp/worklog-test --input examples/mixed-session.json
python3 worklog/scripts/reindex_worklog.py --root /tmp/worklog-test
python3 tools/package_skill.py worklog ./dist
```

GitHub Actions 会校验 skill 结构、编译脚本、跑端到端烟雾测试，并打包 skill。

## 许可证

MIT
