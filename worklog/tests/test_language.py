#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "worklog" / "scripts"))

from worklog_lib import (  # noqa: E402
    DEFAULT_LANGUAGE,
    SUPPORTED_LANGUAGES,
    majority_language,
    normalize_language,
    render_experiences_md,
    render_index_md,
    render_outputs,
    render_worklog_body,
    t,
    validate_payload,
)

FINISH_SCRIPT = REPO_ROOT / "worklog" / "scripts" / "finish_worklog.py"


class HelpersTests(unittest.TestCase):
    def test_t_known_language(self) -> None:
        self.assertEqual(t("zh", "h.timeline"), "主线时间线")
        self.assertEqual(t("en", "h.timeline"), "Timeline")

    def test_t_unknown_language_falls_back_to_default(self) -> None:
        self.assertEqual(t("fr", "h.timeline"), t(DEFAULT_LANGUAGE, "h.timeline"))
        self.assertEqual(t(None, "h.timeline"), t(DEFAULT_LANGUAGE, "h.timeline"))

    def test_t_unknown_key_echoes(self) -> None:
        self.assertEqual(t("zh", "h.no_such_key"), "h.no_such_key")
        self.assertEqual(t("en", "h.no_such_key"), "h.no_such_key")

    def test_normalize_language(self) -> None:
        self.assertEqual(normalize_language("zh"), "zh")
        self.assertEqual(normalize_language("en"), "en")
        self.assertEqual(normalize_language("fr"), DEFAULT_LANGUAGE)
        self.assertEqual(normalize_language(None), DEFAULT_LANGUAGE)
        self.assertEqual(normalize_language(123), DEFAULT_LANGUAGE)

    def test_majority_language_zh_wins(self) -> None:
        self.assertEqual(
            majority_language([{"language": "zh"}, {"language": "zh"}, {"language": "en"}]),
            "zh",
        )

    def test_majority_language_en_wins_when_clear(self) -> None:
        self.assertEqual(
            majority_language([{"language": "en"}, {"language": "en"}]),
            "en",
        )

    def test_majority_language_tie_picks_default(self) -> None:
        self.assertEqual(
            majority_language([{"language": "zh"}, {"language": "en"}]),
            DEFAULT_LANGUAGE,
        )

    def test_majority_language_missing_field_counts_as_default(self) -> None:
        self.assertEqual(majority_language([{}]), DEFAULT_LANGUAGE)
        self.assertEqual(majority_language([]), DEFAULT_LANGUAGE)


class RenderTests(unittest.TestCase):
    def test_mixed_mode_zh_headers(self) -> None:
        payload = {
            "mode": "mixed",
            "language": "zh",
            "sections": {
                "timeline": ["a"],
                "key_decisions": [{"time": "t", "decision": "d", "why": "w"}],
                "outputs": {"code": "c", "knowledge": "k", "remaining": "r"},
                "experience_candidates": ["e"],
            },
        }
        body = render_worklog_body(payload)
        for header in ("## 主线时间线", "## 关键决策", "## 产出", "## 经验候选"):
            self.assertIn(header, body)
        self.assertIn("| 时间 | 决策 | 原因 |", body)

    def test_mixed_mode_defaults_to_zh_when_missing_language(self) -> None:
        payload = {
            "mode": "mixed",
            "sections": {
                "timeline": [],
                "outputs": {"code": "", "knowledge": "", "remaining": ""},
                "experience_candidates": [],
            },
        }
        body = render_worklog_body(payload)
        self.assertIn("## 主线时间线", body)

    def test_dev_mode_en_headers(self) -> None:
        payload = {
            "mode": "dev",
            "language": "en",
            "sections": {
                "goal": "g",
                "completed": [],
                "key_decisions": [],
                "learned": [],
                "remaining_todos": [],
                "references": [],
            },
        }
        body = render_worklog_body(payload)
        for header in ("## Goal", "## Completed", "## Key decisions", "## References"):
            self.assertIn(header, body)

    def test_dev_mode_zh_headers(self) -> None:
        payload = {
            "mode": "dev",
            "language": "zh",
            "sections": {"goal": "g", "completed": [], "key_decisions": [], "learned": [], "remaining_todos": [], "references": []},
        }
        body = render_worklog_body(payload)
        self.assertIn("## 目标", body)
        self.assertIn("## 完成情况", body)
        self.assertIn("## 关键决策", body)

    def test_read_mode_zh_headers(self) -> None:
        payload = {
            "mode": "read",
            "language": "zh",
            "sections": {
                "reading_goal": "g",
                "entry_points": [],
                "mental_model": "m",
                "key_findings": [],
                "open_questions": [],
                "evidence": [],
                "follow_on_output": [],
            },
        }
        body = render_worklog_body(payload)
        self.assertIn("## 阅读目标", body)
        self.assertIn("## 一句话心智模型", body)

    def test_debug_session_zh_headers(self) -> None:
        payload = {
            "mode": "debug-session",
            "language": "zh",
            "sections": {
                "prior_sessions": [],
                "progress": [],
                "current_status": "s",
                "resume_here": [],
                "hypothesis_summary": [],
                "experience_candidates": [],
            },
        }
        body = render_worklog_body(payload)
        self.assertIn("## 历次会话", body)
        self.assertIn("## 假设池摘要", body)

    def test_render_outputs_zh(self) -> None:
        out = render_outputs({"code": "a", "knowledge": "b", "remaining": "c"}, "zh")
        self.assertIn("- 代码: a", out)
        self.assertIn("- 知识: b", out)
        self.assertIn("- 遗留: c", out)

    def test_render_outputs_en(self) -> None:
        out = render_outputs({"code": "a", "knowledge": "b", "remaining": "c"}, "en")
        self.assertIn("- Code: a", out)
        self.assertIn("- Knowledge: b", out)
        self.assertIn("- Remaining: c", out)

    def test_render_index_md_zh(self) -> None:
        md = render_index_md([], "zh")
        self.assertTrue(md.startswith("# 工作日志索引"))

    def test_render_index_md_en(self) -> None:
        md = render_index_md([], "en")
        self.assertTrue(md.startswith("# Work Log Index"))

    def test_render_experiences_md_zh(self) -> None:
        md = render_experiences_md([], "zh")
        self.assertIn("# 经验库", md)
        self.assertIn("最新优先", md)
        self.assertIn("## 标签索引", md)
        self.assertIn("- 无", md)

    def test_render_experiences_md_en(self) -> None:
        md = render_experiences_md([], "en")
        self.assertIn("# Experience Library", md)
        self.assertIn("Newest first", md)
        self.assertIn("## Tag index", md)
        self.assertIn("- None", md)


class ValidationTests(unittest.TestCase):
    def _payload(self, **overrides) -> dict:
        base = {
            "mode": "mixed",
            "project_path": "/tmp/x",
            "title": "t",
            "started_at": "2026-05-17T01:00:00+08:00",
            "duration_minutes": 1,
            "status": "completed",
            "tags": [],
            "original_goal": "g",
            "final_outcome": "f",
            "primary_type": "dev",
            "sections": {
                "timeline": [],
                "outputs": {"code": "", "knowledge": "", "remaining": ""},
                "experience_candidates": [],
            },
        }
        base.update(overrides)
        return base

    def test_accepts_zh(self) -> None:
        validate_payload(self._payload(language="zh"))

    def test_accepts_en(self) -> None:
        validate_payload(self._payload(language="en"))

    def test_rejects_unsupported(self) -> None:
        with self.assertRaises(SystemExit):
            validate_payload(self._payload(language="fr"))

    def test_defaults_when_missing(self) -> None:
        payload = self._payload()
        validate_payload(payload)
        self.assertEqual(payload["language"], DEFAULT_LANGUAGE)


class EndToEndTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="wl-lang-e2e-"))
        (self.tmp / ".git").mkdir()

    def tearDown(self) -> None:
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _run_finish(self, payload: dict) -> Path:
        result = subprocess.run(
            [sys.executable, str(FINISH_SCRIPT)],
            input=json.dumps(payload),
            cwd=str(self.tmp),
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return Path(result.stdout.strip())

    def test_zh_payload_writes_chinese_markdown(self) -> None:
        output = self._run_finish({
            "mode": "mixed",
            "language": "zh",
            "project_path": str(self.tmp),
            "title": "中文 worklog",
            "started_at": "2026-05-17T01:30:00+08:00",
            "duration_minutes": 5,
            "status": "completed",
            "tags": [],
            "original_goal": "g",
            "final_outcome": "f",
            "primary_type": "dev",
            "sections": {
                "timeline": ["x"],
                "outputs": {"code": "c", "knowledge": "k", "remaining": "r"},
                "experience_candidates": [],
            },
        })
        text = output.read_text(encoding="utf-8")
        self.assertIn('language: "zh"', text)
        self.assertIn("## 主线时间线", text)
        self.assertIn("## 产出", text)
        self.assertIn("- 代码: c", text)
        index_text = (self.tmp / ".worklog" / "INDEX.md").read_text(encoding="utf-8")
        self.assertTrue(index_text.startswith("# 工作日志索引"))
        exp_text = (self.tmp / ".worklog" / "EXPERIENCES.md").read_text(encoding="utf-8")
        self.assertIn("# 经验库", exp_text)

    def test_indexes_flip_to_en_when_majority(self) -> None:
        for i in range(2):
            self._run_finish({
                "mode": "mixed",
                "language": "en",
                "project_path": str(self.tmp),
                "title": f"En log {i}",
                "started_at": f"2026-05-17T01:0{i}:00+08:00",
                "duration_minutes": 1,
                "status": "completed",
                "tags": [],
                "original_goal": "g",
                "final_outcome": "f",
                "primary_type": "dev",
                "sections": {
                    "timeline": ["x"],
                    "outputs": {"code": "", "knowledge": "", "remaining": ""},
                    "experience_candidates": [],
                },
            })
        self._run_finish({
            "mode": "mixed",
            "language": "zh",
            "project_path": str(self.tmp),
            "title": "中文 log",
            "started_at": "2026-05-17T01:30:00+08:00",
            "duration_minutes": 1,
            "status": "completed",
            "tags": [],
            "original_goal": "g",
            "final_outcome": "f",
            "primary_type": "dev",
            "sections": {
                "timeline": [],
                "outputs": {"code": "", "knowledge": "", "remaining": ""},
                "experience_candidates": [],
            },
        })
        index_text = (self.tmp / ".worklog" / "INDEX.md").read_text(encoding="utf-8")
        self.assertTrue(index_text.startswith("# Work Log Index"))


if __name__ == "__main__":
    unittest.main()
