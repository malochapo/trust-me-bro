"""The real arms: each setup.sh in a fresh HOME against a tiny repo, then its probe.

Skipped for an arm whose tool is not installed (arms/install.sh). Uses run.py's own
setup, probe and daemon helpers, so this is what a run does before `claude -p` starts.
"""

import io
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from support import make_fixture, git

import common
import run

TOOLS = Path(os.environ.get("BENCH_TOOLS", str(Path.home() / ".cache/sobre-bench/tools")))


def installed(arm):
    entry = common.arm_version(arm) or {}
    return not entry.get("binary") or (TOOLS / "bin" / entry["binary"]).exists()


class ArmSetupTest(unittest.TestCase):
    def setup_arm(self, arm):
        if not installed(arm):
            self.skipTest(f"{arm} is not installed in {TOOLS}")
        tmp = Path(self.enterContext(tempfile.TemporaryDirectory()))
        repo, home, toolbin = tmp / "repo", tmp / "home", tmp / "bin"
        git("clone", "-q", str(make_fixture(tmp)), str(repo), cwd=tmp)
        (repo / "app.py").write_text("def f():\n    return 1\n")
        git("add", "-A", cwd=repo)
        git("-c", "user.name=t", "-c", "user.email=t@example.com", "commit", "-qm", "app", cwd=repo)
        (home / ".claude").mkdir(parents=True)
        run.make_toolbin(toolbin, arm, TOOLS)
        env = common.clean_env(home, [toolbin] + common.SYSTEM_PATH, {"REPO": str(repo), "BENCH_TOOLS": str(TOOLS)})
        log = io.StringIO()
        try:
            rc, extra, _ = run.run_setup(common.ARMS_DIR / arm, env, home, log)
            self.assertEqual(rc, 0, log.getvalue())
            probe = run.run_probe(common.ARMS_DIR / arm, env, repo)
        finally:
            daemon = run.stop_daemon(home)
        self.assertIn(daemon, (None, "stopped"))
        self.assertEqual(git_status(repo), "", "setup wrote into the repo")
        settings = json.loads((home / ".claude/settings.json").read_text())
        servers = json.loads((home / "mcp.json").read_text())["mcpServers"]
        return extra, settings, servers, probe, home

    def test_native(self):
        extra, settings, servers, probe, _ = self.setup_arm("native")
        self.assertEqual((extra, settings, servers, probe), ({}, {}, {}, {}))

    def test_sobre(self):
        extra, settings, servers, probe, _ = self.setup_arm("sobre")
        self.assertEqual(extra, {})
        self.assertEqual(list(servers), ["sobre"])
        commands = hook_commands(settings)
        self.assertIn(("PostToolUse", "Bash", "sobre hook compress"), commands)
        self.assertIn(("PostToolUse", "Read", "sobre hook read-dedup"), commands)
        self.assertIn(("UserPromptSubmit", ".*", "sobre hook observe"), commands)
        self.assertIs(probe["active"], False)  # nothing ran yet

    def test_rtk(self):
        extra, settings, servers, probe, home = self.setup_arm("rtk")
        self.assertEqual((extra, servers), ({}, {}))
        self.assertIn(("PreToolUse", "Bash", "rtk hook claude"), hook_commands(settings))
        self.assertIn("@RTK.md", (home / ".claude/CLAUDE.md").read_text())
        self.assertIs(probe["active"], False)

    def test_lean_ctx(self):
        extra, settings, servers, probe, _ = self.setup_arm("lean-ctx")
        self.assertEqual(list(servers), ["lean-ctx"])
        self.assertIn(("PreToolUse", "Bash|bash", "lean-ctx hook rewrite"), hook_commands(settings))
        self.assertEqual(settings["permissions"]["deny"], ["Grep", "Glob"])
        self.assertIs(probe["active"], False)

    def test_headroom(self):
        extra, settings, servers, probe, home = self.setup_arm("headroom")
        port = (home / "arm.port").read_text().strip()
        self.assertEqual(extra, {"ANTHROPIC_BASE_URL": f"http://127.0.0.1:{port}", "ENABLE_TOOL_SEARCH": "true"})
        self.assertEqual((settings, servers), ({}, {}))
        self.assertEqual(probe["api_requests"], 0)  # the proxy answered /stats while it ran
        # [sandbox] install: Kompress runs on ONNX, and code-aware (tree-sitter) compression is on.
        self.assertEqual(probe["kompress"], {"ready": True, "status": "healthy", "backend": "onnx"})
        self.assertEqual(probe["code_aware"], "ENABLED")


def hook_commands(settings):
    """(event, matcher, command without the binary's directory) for every hook."""
    out = []
    for event, groups in settings.get("hooks", {}).items():
        for group in groups:
            for hook in group.get("hooks", []):
                out.append((event, group.get("matcher"), hook["command"].rsplit("/", 1)[-1]))
    return out


def git_status(repo):
    return subprocess.run(["git", "status", "--porcelain"], cwd=repo, capture_output=True, text=True).stdout


if __name__ == "__main__":
    unittest.main()
