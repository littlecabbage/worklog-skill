#!/usr/bin/env python3
from __future__ import annotations

import json
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
    t,
)

FINISH_SCRIPT = REPO_ROOT / "worklog" / "scripts" / "finish_worklog.py"


class HelpersTests(unittest.TestCase):
    def test_t_known_language(self) -> None:
        self.assertEqual(t("zh", "index.title"), "工作日志索引")
        self.assertEqual(t("en", "index.title"), "Work Log Index")

    def test_t_unknown_language_falls_back_to_default(self) -> None:
        self.assertEqual(t("fr", "index.title"), t(DEFAULT_LANGUAGE, "index.title"))
        self.assertEqual(t(None, "index.title"), t(DEFAULT_LANGUAGE, "index.title"))

    def test_t_unknown_key_echoes(self) -> None:
        self.assertEqual(t("zh", "no_such_key"), "no_such_key")
        self.assertEqual(t("en", "no_such_key"), "no_such_key")

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


class StructuralRenderTests(unittest.TestCase):
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

    def test_zh_payload_writes_chinese_indexes(self) -> None:
        self._run_finish({
            "mode": "mixed",
            "language": "zh",
            "project_path": str(self.tmp),
            "title": "中文 worklog",
            "started_at": "2026-05-17T01:30:00+08:00",
            "duration_minutes": 5,
            "status": "completed",
            "tags": [],
            "summary": "中文摘要：写一个 worklog 验证语言处理。",
            "body": "## 主线时间线\n\n- 起步\n- 写入\n",
        })
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
                "summary": "English worklog summary for majority test.",
                "body": "## Timeline\n\n- did some english things\n",
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
            "summary": "一个中文 worklog 用作少数语言。",
            "body": "## 主线\n\n- 中文记录\n",
        })
        index_text = (self.tmp / ".worklog" / "INDEX.md").read_text(encoding="utf-8")
        self.assertTrue(index_text.startswith("# Work Log Index"))


if __name__ == "__main__":
    unittest.main()
