#!/usr/bin/env python3
from __future__ import annotations

import concurrent.futures
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPT = REPO_ROOT / "worklog" / "scripts" / "capture_hook.py"


def run_hook(event_type: str, payload: dict, env_extra: dict | None = None) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    if env_extra:
        env.update(env_extra)
    return subprocess.run(
        [sys.executable, str(SCRIPT), event_type],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        env=env,
        timeout=10,
    )


def read_events(draft_dir: Path) -> list[dict]:
    path = draft_dir / "events.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


class CaptureHookTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.mkdtemp(prefix="wl-test-")
        self.cwd = Path(self.tmp)

    def tearDown(self) -> None:
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def draft_dir(self, sid: str) -> Path:
        return self.cwd / ".worklog" / "draft" / sid

    def test_basic_prompt_write(self) -> None:
        result = run_hook(
            "user_prompt_submit",
            {"session_id": "sid-1", "cwd": str(self.cwd), "prompt": "hello world"},
        )
        self.assertEqual(result.returncode, 0)
        events = read_events(self.draft_dir("sid-1"))
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["type"], "prompt")
        self.assertEqual(events[0]["display"], "hello world")
        self.assertEqual(events[0]["sid"], "sid-1")
        self.assertIn("ts", events[0])

    def test_tool_event_with_redaction(self) -> None:
        run_hook(
            "post_tool_use",
            {
                "session_id": "sid-2",
                "cwd": str(self.cwd),
                "tool_name": "Edit",
                "tool_input": {"file_path": "/some/path/.env.production"},
                "tool_response": {},
            },
        )
        events = read_events(self.draft_dir("sid-2"))
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["target"], "<redacted>")
        self.assertTrue(events[0]["ok"])

    def test_tool_event_keeps_normal_path(self) -> None:
        run_hook(
            "post_tool_use",
            {
                "session_id": "sid-3",
                "cwd": str(self.cwd),
                "tool_name": "Edit",
                "tool_input": {"file_path": "app/user.py"},
                "tool_response": {"error": None},
            },
        )
        events = read_events(self.draft_dir("sid-3"))
        self.assertEqual(events[0]["target"], "app/user.py")

    def test_tool_failure_marks_ok_false(self) -> None:
        run_hook(
            "post_tool_use",
            {
                "session_id": "sid-3b",
                "cwd": str(self.cwd),
                "tool_name": "Bash",
                "tool_input": {"command": "false"},
                "tool_response": {"error": "exit 1"},
            },
        )
        events = read_events(self.draft_dir("sid-3b"))
        self.assertFalse(events[0]["ok"])

    def test_truncate_long_prompt(self) -> None:
        long_text = "x" * 1000
        run_hook(
            "user_prompt_submit",
            {"session_id": "sid-4", "cwd": str(self.cwd), "prompt": long_text},
        )
        events = read_events(self.draft_dir("sid-4"))
        display = events[0]["display"]
        self.assertLessEqual(len(display), 501)
        self.assertTrue(display.endswith("…"))

    def test_recursion_guard_blocks_write(self) -> None:
        run_hook(
            "user_prompt_submit",
            {"session_id": "sid-5", "cwd": str(self.cwd), "prompt": "should not write"},
            env_extra={"WORKLOG_HOOK_ACTIVE": "1"},
        )
        self.assertFalse(self.draft_dir("sid-5").exists())

    def test_silent_failure_on_invalid_stdin(self) -> None:
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "user_prompt_submit"],
            input="not json at all",
            text=True,
            capture_output=True,
            timeout=10,
        )
        self.assertEqual(result.returncode, 0)
        self.assertFalse((self.cwd / ".worklog").exists())

    def test_unknown_event_type_is_noop(self) -> None:
        result = run_hook(
            "garbage_event",
            {"session_id": "sid-x", "cwd": str(self.cwd), "prompt": "x"},
        )
        self.assertEqual(result.returncode, 0)
        self.assertFalse(self.draft_dir("sid-x").exists())

    def test_missing_session_id_or_cwd_is_silent(self) -> None:
        run_hook("user_prompt_submit", {"cwd": str(self.cwd), "prompt": "x"})
        run_hook("user_prompt_submit", {"session_id": "sid-y", "prompt": "x"})
        self.assertFalse((self.cwd / ".worklog").exists())

    def test_multi_session_isolation(self) -> None:
        run_hook(
            "user_prompt_submit",
            {"session_id": "sid-A", "cwd": str(self.cwd), "prompt": "from A"},
        )
        run_hook(
            "user_prompt_submit",
            {"session_id": "sid-B", "cwd": str(self.cwd), "prompt": "from B"},
        )
        events_a = read_events(self.draft_dir("sid-A"))
        events_b = read_events(self.draft_dir("sid-B"))
        self.assertEqual(len(events_a), 1)
        self.assertEqual(len(events_b), 1)
        self.assertEqual(events_a[0]["display"], "from A")
        self.assertEqual(events_b[0]["display"], "from B")

    def test_concurrent_appends_do_not_corrupt(self) -> None:
        N = 50
        payloads = [
            {
                "session_id": "sid-concurrent",
                "cwd": str(self.cwd),
                "tool_name": "Bash",
                "tool_input": {"command": f"echo {i}"},
                "tool_response": {},
            }
            for i in range(N)
        ]
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as pool:
            list(pool.map(lambda p: run_hook("post_tool_use", p), payloads))
        events = read_events(self.draft_dir("sid-concurrent"))
        self.assertEqual(len(events), N)
        commands = sorted(e["target"] for e in events)
        expected = sorted(f"echo {i}" for i in range(N))
        self.assertEqual(commands, expected)


if __name__ == "__main__":
    unittest.main()
