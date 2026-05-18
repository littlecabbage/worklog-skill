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
    detect_language_from_body,
    flatten_meta,
    is_body_payload,
    validate_body_payload,
)

FINISH_SCRIPT = REPO_ROOT / "worklog" / "scripts" / "finish_worklog.py"


def make_workspace() -> tempfile.TemporaryDirectory:
    """Create a temp directory and `git init` it so the script picks up a project root."""
    tmp = tempfile.TemporaryDirectory()
    subprocess.run(["git", "init", "-q"], cwd=tmp.name, check=True)
    return tmp


def run_finish(payload: dict, cwd: str, validate_only: bool = False) -> subprocess.CompletedProcess:
    args = [sys.executable, str(FINISH_SCRIPT)]
    if validate_only:
        args.append("--validate-only")
    return subprocess.run(
        args,
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        cwd=cwd,
    )


def base_body_payload(**overrides) -> dict:
    payload = {
        "mode": "dev",
        "title": "Body smoke",
        "status": "completed",
        "started_at": "2026-05-18T10:00:00+08:00",
        "duration_minutes": 30,
        "tags": ["smoke"],
        "language": "en",
        "summary": "Verify the body-first payload writes a worklog and surfaces summary into index.json.",
        "body": "## Goal\n\nMake sure the script accepts free-form markdown.\n\n## Done\n\n- wrote body\n",
    }
    payload.update(overrides)
    return payload


class DispatchTests(unittest.TestCase):
    def test_is_body_payload_recognized_even_when_blank(self) -> None:
        self.assertTrue(is_body_payload({"body": "hi"}))
        self.assertTrue(is_body_payload({"body": "   "}))
        self.assertFalse(is_body_payload({"sections": {"goal": "x"}}))


class LanguageDetectionTests(unittest.TestCase):
    def test_predominantly_chinese(self) -> None:
        self.assertEqual(detect_language_from_body("## 目标\n\n做一些中文的事情，验证检测能力。"), "zh")

    def test_predominantly_english(self) -> None:
        self.assertEqual(
            detect_language_from_body("## Goal\n\nMake sure the script accepts free-form markdown."),
            "en",
        )

    def test_short_punctuation_only_falls_back_to_default(self) -> None:
        self.assertEqual(detect_language_from_body("---\n\n###"), "zh")

    def test_payload_omitting_language_picks_zh_for_chinese_body(self) -> None:
        payload = base_body_payload(
            body="## 目标\n\n做一些中文的事情，验证检测能力\n\n## 完成\n\n- 测试通过",
            summary="中文摘要描述",
        )
        del payload["language"]
        validate_body_payload(payload)
        self.assertEqual(payload["language"], "zh")

    def test_payload_omitting_language_picks_en_for_english_body(self) -> None:
        payload = base_body_payload()
        del payload["language"]
        validate_body_payload(payload)
        self.assertEqual(payload["language"], "en")


class FlattenMetaTests(unittest.TestCase):
    def test_flat_meta_pulled_to_top(self) -> None:
        payload = base_body_payload(meta={"branch": "main", "pr_url": "https://x/1"})
        out, warnings = flatten_meta(payload)
        self.assertEqual(out["branch"], "main")
        self.assertEqual(out["pr_url"], "https://x/1")
        self.assertEqual(warnings, [])
        self.assertNotIn("meta", out)

    def test_nested_meta_under_mode_pulled_to_top(self) -> None:
        payload = base_body_payload(meta={"dev": {"branch": "feat", "pr_url": "https://x/2"}})
        out, warnings = flatten_meta(payload)
        self.assertEqual(out["branch"], "feat")
        self.assertEqual(out["pr_url"], "https://x/2")
        self.assertEqual(warnings, [])

    def test_unknown_meta_key_warns(self) -> None:
        payload = base_body_payload(meta={"branch": "main", "made_up_field": "x"})
        _, warnings = flatten_meta(payload)
        self.assertEqual(len(warnings), 1)
        self.assertIn("made_up_field", warnings[0])

    def test_unknown_nested_meta_key_warns(self) -> None:
        payload = base_body_payload(meta={"dev": {"branch": "main", "weird": 1}})
        _, warnings = flatten_meta(payload)
        self.assertTrue(any("meta.dev.weird" in w for w in warnings))

    def test_meta_must_be_object(self) -> None:
        payload = base_body_payload(meta="not an object")
        with self.assertRaises(SystemExit):
            flatten_meta(payload)


class ValidationTests(unittest.TestCase):
    def test_accepts_minimal_body_payload(self) -> None:
        payload = base_body_payload()
        warnings = validate_body_payload(payload)
        self.assertEqual(warnings, [])

    def test_rejects_empty_body(self) -> None:
        with self.assertRaises(SystemExit):
            validate_body_payload(base_body_payload(body="   "))

    def test_rejects_body_starting_with_frontmatter_fence(self) -> None:
        with self.assertRaises(SystemExit):
            validate_body_payload(base_body_payload(body="---\nfoo: bar\n---\nhi"))

    def test_rejects_missing_summary(self) -> None:
        payload = base_body_payload()
        del payload["summary"]
        with self.assertRaises(SystemExit):
            validate_body_payload(payload)

    def test_rejects_blank_summary(self) -> None:
        with self.assertRaises(SystemExit):
            validate_body_payload(base_body_payload(summary="   "))

    def test_rejects_search_keywords_not_array(self) -> None:
        with self.assertRaises(SystemExit):
            validate_body_payload(base_body_payload(search_keywords="not a list"))

    def test_rejects_non_string_search_keyword(self) -> None:
        with self.assertRaises(SystemExit):
            validate_body_payload(base_body_payload(search_keywords=["ok", 42]))

    def test_unknown_top_level_key_warns(self) -> None:
        payload = base_body_payload()
        payload["surprise_field"] = "kept"
        warnings = validate_body_payload(payload)
        self.assertTrue(any("surprise_field" in w for w in warnings))


class EndToEndTests(unittest.TestCase):
    def test_body_payload_writes_file_and_indexes(self) -> None:
        with make_workspace() as tmp:
            result = run_finish(base_body_payload(), cwd=tmp)
            self.assertEqual(result.returncode, 0, result.stderr)
            output_path = Path(result.stdout.strip())
            self.assertTrue(output_path.exists())
            content = output_path.read_text(encoding="utf-8")
            self.assertIn("## Goal", content)
            self.assertIn('summary: "Verify the body-first payload', content)

            index = json.loads((Path(tmp) / ".worklog" / "index.json").read_text(encoding="utf-8"))
            self.assertEqual(len(index["worklogs"]), 1)
            entry = index["worklogs"][0]
            self.assertEqual(entry["summary"], base_body_payload()["summary"])
            self.assertIn("smoke", entry["tags"])

    def test_body_payload_with_meta_lands_in_frontmatter_and_index(self) -> None:
        payload = base_body_payload(meta={"branch": "feat", "pr_url": "https://example.com/pr/9"})
        with make_workspace() as tmp:
            result = run_finish(payload, cwd=tmp)
            self.assertEqual(result.returncode, 0, result.stderr)
            index = json.loads((Path(tmp) / ".worklog" / "index.json").read_text(encoding="utf-8"))
            entry = index["worklogs"][0]
            self.assertEqual(entry["branch"], "feat")
            self.assertEqual(entry["pr_url"], "https://example.com/pr/9")

    def test_legacy_sections_payload_now_rejected(self) -> None:
        payload = {
            "mode": "dev",
            "title": "Legacy sections",
            "status": "completed",
            "started_at": "2026-05-18T10:00:00+08:00",
            "duration_minutes": 5,
            "tags": ["legacy"],
            "language": "en",
            "sections": {
                "goal": "Stay backward-compatible",
                "completed": ["wrote test"],
            },
        }
        with make_workspace() as tmp:
            result = run_finish(payload, cwd=tmp)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("legacy `sections`", result.stderr)
            self.assertFalse((Path(tmp) / ".worklog").exists())

    def test_validate_only_does_not_write(self) -> None:
        with make_workspace() as tmp:
            result = run_finish(base_body_payload(), cwd=tmp, validate_only=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.strip(), "ok")
            self.assertFalse((Path(tmp) / ".worklog" / "index.json").exists())

    def test_invalid_body_payload_exits_nonzero(self) -> None:
        bad = base_body_payload(body="   ")
        with make_workspace() as tmp:
            result = run_finish(bad, cwd=tmp)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("body", result.stderr)

    def test_body_with_leading_frontmatter_fence_rejected(self) -> None:
        with make_workspace() as tmp:
            result = run_finish(
                base_body_payload(body="---\nfoo: bar\n---\nhi"),
                cwd=tmp,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("frontmatter fence", result.stderr)

    def test_reindex_preserves_extended_whitelist_fields(self) -> None:
        with make_workspace() as tmp:
            run_finish(
                base_body_payload(meta={"branch": "feat", "pr_url": "https://x/1"}),
                cwd=tmp,
            )
            subprocess.run(
                [sys.executable, str(REPO_ROOT / "worklog" / "scripts" / "reindex_worklog.py")],
                cwd=tmp,
                check=True,
                capture_output=True,
            )
            index = json.loads((Path(tmp) / ".worklog" / "index.json").read_text(encoding="utf-8"))
            entry = index["worklogs"][0]
            self.assertEqual(entry["branch"], "feat")
            self.assertEqual(entry["pr_url"], "https://x/1")
            self.assertEqual(
                entry["summary"],
                base_body_payload()["summary"],
            )

    def test_language_does_not_silently_revert_to_zh(self) -> None:
        payload = base_body_payload()
        with make_workspace() as tmp:
            result = run_finish(payload, cwd=tmp)
            self.assertEqual(result.returncode, 0, result.stderr)
            index = json.loads((Path(tmp) / ".worklog" / "index.json").read_text(encoding="utf-8"))
            self.assertEqual(index["worklogs"][0]["language"], "en")


if __name__ == "__main__":
    unittest.main()
