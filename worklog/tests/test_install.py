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
HOOKS_INSTALL = REPO_ROOT / "worklog" / "scripts" / "hooks_install.py"
INIT_WORKLOG = REPO_ROOT / "worklog" / "scripts" / "init_worklog.py"


def run(script: Path, *args: str, cwd: Path, home: Path) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["HOME"] = str(home)
    return subprocess.run(
        [sys.executable, str(script), *args],
        cwd=str(cwd),
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )


def fake_git_init(path: Path) -> None:
    (path / ".git").mkdir(parents=True, exist_ok=True)


def shim_for(home: Path) -> Path:
    return home / ".claude" / "hooks" / "worklog-capture.sh"


def settings_for(project: Path) -> Path:
    return project / ".claude" / "settings.local.json"


def global_settings_for(home: Path) -> Path:
    return home / ".claude" / "settings.json"


class HooksInstallTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="wl-install-"))
        self.project = self.tmp / "project"
        self.home = self.tmp / "home"
        self.project.mkdir()
        self.home.mkdir()
        fake_git_init(self.project)

    def tearDown(self) -> None:
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_install_creates_shim_and_settings(self) -> None:
        result = run(HOOKS_INSTALL, cwd=self.project, home=self.home)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(shim_for(self.home).exists())
        self.assertTrue(os.access(shim_for(self.home), os.X_OK))
        settings = json.loads(settings_for(self.project).read_text())
        for event in ("UserPromptSubmit", "PostToolUse", "Stop"):
            self.assertIn(event, settings["hooks"])
            commands = [
                inner["command"]
                for bucket in settings["hooks"][event]
                for inner in bucket["hooks"]
            ]
            self.assertTrue(any("worklog-capture.sh" in c for c in commands))

    def test_install_preserves_existing_permissions(self) -> None:
        settings_path = settings_for(self.project)
        settings_path.parent.mkdir(parents=True)
        settings_path.write_text(json.dumps({
            "permissions": {"allow": ["Bash(ls *)"]},
        }))
        run(HOOKS_INSTALL, cwd=self.project, home=self.home)
        merged = json.loads(settings_path.read_text())
        self.assertEqual(merged["permissions"]["allow"], ["Bash(ls *)"])
        self.assertIn("hooks", merged)

    def test_install_preserves_other_hooks(self) -> None:
        settings_path = settings_for(self.project)
        settings_path.parent.mkdir(parents=True)
        settings_path.write_text(json.dumps({
            "hooks": {
                "PostToolUse": [
                    {
                        "matcher": "Bash",
                        "hooks": [
                            {"type": "command", "command": "$HOME/.claude/hooks/gsd-something.sh"}
                        ],
                    }
                ]
            }
        }))
        run(HOOKS_INSTALL, cwd=self.project, home=self.home)
        merged = json.loads(settings_path.read_text())
        post = merged["hooks"]["PostToolUse"]
        self.assertEqual(len(post), 2)
        commands = [inner["command"] for bucket in post for inner in bucket["hooks"]]
        self.assertTrue(any("gsd-something.sh" in c for c in commands))
        self.assertTrue(any("worklog-capture.sh" in c for c in commands))

    def test_install_idempotent(self) -> None:
        run(HOOKS_INSTALL, cwd=self.project, home=self.home)
        first = settings_for(self.project).read_text()
        result = run(HOOKS_INSTALL, cwd=self.project, home=self.home)
        second = settings_for(self.project).read_text()
        self.assertEqual(first, second)
        self.assertIn("already installed", result.stdout)

    def test_dry_run_writes_nothing(self) -> None:
        run(HOOKS_INSTALL, "--dry-run", cwd=self.project, home=self.home)
        self.assertFalse(shim_for(self.home).exists())
        self.assertFalse(settings_for(self.project).exists())

    def test_uninstall_removes_only_worklog_entries(self) -> None:
        settings_path = settings_for(self.project)
        settings_path.parent.mkdir(parents=True)
        settings_path.write_text(json.dumps({
            "hooks": {
                "Stop": [
                    {"hooks": [{"type": "command", "command": "$HOME/.claude/hooks/gsd-stop.sh"}]}
                ]
            },
            "permissions": {"allow": ["Bash(ls *)"]},
        }))
        run(HOOKS_INSTALL, cwd=self.project, home=self.home)
        run(HOOKS_INSTALL, "--uninstall", cwd=self.project, home=self.home)
        merged = json.loads(settings_path.read_text())
        self.assertEqual(merged["permissions"]["allow"], ["Bash(ls *)"])
        self.assertIn("Stop", merged["hooks"])
        stop_commands = [
            inner["command"]
            for bucket in merged["hooks"]["Stop"]
            for inner in bucket["hooks"]
        ]
        self.assertTrue(all("worklog-capture.sh" not in c for c in stop_commands))
        self.assertTrue(any("gsd-stop.sh" in c for c in stop_commands))

    def test_uninstall_removes_shim(self) -> None:
        run(HOOKS_INSTALL, cwd=self.project, home=self.home)
        self.assertTrue(shim_for(self.home).exists())
        run(HOOKS_INSTALL, "--uninstall", cwd=self.project, home=self.home)
        self.assertFalse(shim_for(self.home).exists())

    def test_global_scope_writes_to_home_settings(self) -> None:
        run(HOOKS_INSTALL, "--global", cwd=self.project, home=self.home)
        self.assertTrue(global_settings_for(self.home).exists())
        self.assertFalse(settings_for(self.project).exists())


class InitWorklogTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="wl-init-"))
        self.project = self.tmp / "project"
        self.home = self.tmp / "home"
        self.project.mkdir()
        self.home.mkdir()
        fake_git_init(self.project)

    def tearDown(self) -> None:
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_init_creates_full_layout(self) -> None:
        result = run(INIT_WORKLOG, cwd=self.project, home=self.home)
        self.assertEqual(result.returncode, 0, result.stderr)
        worklog = self.project / ".worklog"
        self.assertTrue((worklog / "INDEX.md").exists())
        self.assertTrue((worklog / "EXPERIENCES.md").exists())
        self.assertTrue((worklog / "index.json").exists())
        self.assertTrue((worklog / "archive").is_dir())
        self.assertTrue(shim_for(self.home).exists())
        settings = json.loads(settings_for(self.project).read_text())
        self.assertIn("UserPromptSubmit", settings["hooks"])
        gitignore = (self.project / ".gitignore").read_text()
        self.assertIn("/.worklog/draft/", gitignore)

    def test_init_idempotent(self) -> None:
        run(INIT_WORKLOG, cwd=self.project, home=self.home)
        first_settings = settings_for(self.project).read_text()
        first_gitignore = (self.project / ".gitignore").read_text()
        result = run(INIT_WORKLOG, cwd=self.project, home=self.home)
        self.assertEqual(settings_for(self.project).read_text(), first_settings)
        self.assertEqual((self.project / ".gitignore").read_text(), first_gitignore)
        self.assertIn("unchanged", result.stdout)

    def test_skip_hooks_and_gitignore(self) -> None:
        run(INIT_WORKLOG, "--skip-hooks", "--skip-gitignore", cwd=self.project, home=self.home)
        self.assertFalse(shim_for(self.home).exists())
        self.assertFalse(settings_for(self.project).exists())
        self.assertFalse((self.project / ".gitignore").exists())
        self.assertTrue((self.project / ".worklog" / "INDEX.md").exists())

    def test_uninstall_preserves_worklog_data(self) -> None:
        run(INIT_WORKLOG, cwd=self.project, home=self.home)
        (self.project / ".worklog" / "2026-05-17").mkdir()
        (self.project / ".worklog" / "2026-05-17" / "task.md").write_text("data")
        run(INIT_WORKLOG, "--uninstall", cwd=self.project, home=self.home)
        self.assertFalse(shim_for(self.home).exists())
        self.assertTrue((self.project / ".worklog" / "2026-05-17" / "task.md").exists())
        gitignore = (self.project / ".gitignore").read_text()
        self.assertNotIn("/.worklog/draft/", gitignore)

    def test_gitignore_appends_to_existing(self) -> None:
        (self.project / ".gitignore").write_text("node_modules/\n*.log\n")
        run(INIT_WORKLOG, cwd=self.project, home=self.home)
        gi = (self.project / ".gitignore").read_text()
        self.assertIn("node_modules/", gi)
        self.assertIn("*.log", gi)
        self.assertIn("/.worklog/draft/", gi)

    def test_gitignore_skips_when_broader_rule_present(self) -> None:
        (self.project / ".gitignore").write_text(".worklog/\nnode_modules/\n")
        result = run(INIT_WORKLOG, cwd=self.project, home=self.home)
        gi = (self.project / ".gitignore").read_text()
        self.assertNotIn("/.worklog/draft/", gi)
        self.assertNotIn("worklog capture drafts", gi)
        self.assertIn("covered", result.stdout)

    def test_gitignore_broader_rule_variants(self) -> None:
        for variant in (".worklog", "/.worklog", "/.worklog/", ".worklog/**"):
            with self.subTest(rule=variant):
                gi = self.project / ".gitignore"
                gi.write_text(f"{variant}\n")
                run(INIT_WORKLOG, cwd=self.project, home=self.home)
                self.assertNotIn("/.worklog/draft/", gi.read_text())
                run(INIT_WORKLOG, "--uninstall", cwd=self.project, home=self.home)
                gi.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
