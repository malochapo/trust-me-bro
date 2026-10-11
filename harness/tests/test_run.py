"""run.py end to end with the stub claude: environment isolation, flags, captures, status."""

import json
import subprocess
import os
import tempfile
import unittest
from pathlib import Path

from support import ANSWER, make_arms, make_claude, make_fixture, make_task, run_harness

import run

BASE_ENV_KEYS = {"PATH", "HOME", "CLAUDE_CONFIG_DIR", "LANG", "TERM", "IS_SANDBOX", "DISABLE_AUTOUPDATER"}


class RunTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.fixture = make_fixture(self.root)
        self.task = make_task(self.root)
        self.arms = make_arms(self.root)
        self.out, self.work = self.root / "raw", self.root / "work"
        # The parent's environment leaks everywhere unless run.py starts from nothing.
        self.env = {k: v for k, v in os.environ.items()
                    if k not in ("BENCH_EXTRA_PATH", "BENCH_CLAUDE_OAUTH_TOKEN")}
        self.env.update(CLAUDE_LEAK="leak", ANTHROPIC_BASE_URL="http://leak", ANTHROPIC_API_KEY="leak",
                        HTTPS_PROXY="http://proxy.leak", HTTP_PROXY="http://proxy.leak",
                        CLAUDE_CODE_OAUTH_TOKEN="tok-123", BENCH_LOCK_FILE=str(self.root / "lock"))

    def tearDown(self):
        self._tmp.cleanup()

    def run_arm(self, arm, scenario="ok", extra=()):
        claude, record = make_claude(self.root, scenario)
        r = run_harness("run.py", ["--task-file", self.task, "--arm", arm, "--rep", 1, "--fixture", self.fixture,
                                   "--out", self.out, "--work", self.work, "--claude-bin", claude,
                                   "--arms-dir", self.arms, "--no-venv", "--no-pg-check", *extra], self.env)
        run_id = run.run_id_for(json.loads(Path(self.task).read_text())["id"], arm, 1)
        run_dir = self.out / run_id
        meta = json.loads((run_dir / "meta.json").read_text()) if (run_dir / "meta.json").exists() else None
        rec = json.loads(record.read_text()) if record.exists() else None
        return r, run_dir, meta, rec

    def test_native_env_is_built_from_nothing(self):
        r, run_dir, meta, rec = self.run_arm("native")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(meta["status"], "ok", meta.get("invalid_reason"))
        env = rec["env"]
        self.assertEqual(set(env), BASE_ENV_KEYS | {"CLAUDE_CODE_OAUTH_TOKEN"})
        self.assertEqual(env["CLAUDE_CODE_OAUTH_TOKEN"], "tok-123")
        self.assertFalse([k for k in env if k.startswith("ANTHROPIC") or "PROXY" in k])
        work = self.work / run.work_name(meta["run_id"])
        self.assertEqual(env["HOME"], str(work / "home"))
        self.assertEqual(env["CLAUDE_CONFIG_DIR"], str(work / "home" / ".claude"))
        self.assertEqual(env["PATH"].split(":")[0], str(work / "bin"))
        self.assertEqual(rec["cwd"], str(work / "repo"))
        self.assertNotIn("native", json.dumps(rec))  # no path the agent sees names the arm

    def test_bench_token_wins_and_reaches_claude_only_as_claude_code_oauth_token(self):
        self.env["BENCH_CLAUDE_OAUTH_TOKEN"] = "bench-tok"
        _, _, meta, rec = self.run_arm("native")
        self.assertEqual(meta["status"], "ok")
        self.assertEqual(rec["env"]["CLAUDE_CODE_OAUTH_TOKEN"], "bench-tok")
        self.assertNotIn("BENCH_CLAUDE_OAUTH_TOKEN", rec["env"])
        self.assertNotIn("bench-tok", json.dumps(meta))

    def test_flags_prompt_and_captures(self):
        r, run_dir, meta, rec = self.run_arm("native")
        argv = rec["argv"]
        work = self.work / run.work_name(meta["run_id"])
        self.assertEqual(argv[0], "-p")
        prompt = rec["stdin"]  # on stdin, in no process's argv
        self.assertNotIn(prompt, argv)
        self.assertTrue(meta["isolated"])
        self.assertIn(str(work / "data") + "/app.log", prompt)
        self.assertTrue((work / "data" / "app.log").exists())
        pairs = {argv[i]: argv[i + 1] for i in range(1, len(argv) - 1) if argv[i].startswith("--")}
        self.assertEqual(pairs["--model"], "claude-sonnet-5-5")
        self.assertEqual(pairs["--effort"], "medium")
        self.assertEqual(pairs["--output-format"], "stream-json")
        self.assertEqual(pairs["--setting-sources"], "user")
        self.assertEqual(pairs["--mcp-config"], str(work / "home" / "mcp.json"))
        self.assertEqual(pairs["--permission-mode"], "bypassPermissions")
        self.assertEqual(pairs["--max-turns"], "80")
        self.assertEqual(pairs["--max-budget-usd"], "3")
        self.assertIn("--verbose", argv)
        self.assertIn("--strict-mcp-config", argv)
        self.assertEqual(argv[-3:], ["--disallowedTools", "WebFetch", "WebSearch"])
        self.assertEqual((run_dir / "answer.md").read_text(), ANSWER)
        self.assertEqual((run_dir / "prompt.txt").read_text(), prompt)
        patch = (run_dir / "changes.patch").read_text()
        self.assertIn("#   NOTES.txt", patch)
        self.assertIn("+edited by the agent", patch)
        self.assertIn("+new file from the agent", patch)
        usage = json.loads((run_dir / "usage.json").read_text())
        self.assertAlmostEqual(usage["cost_usd"], 0.024828, places=6)
        self.assertEqual(meta["fixture_head"], meta["fixture_head"].strip())
        self.assertEqual(len(meta["fixture_head"]), 40)
        self.assertIn("stub", meta["claude_version"])
        self.assertEqual(json.loads((run_dir / "probe.json").read_text()), {})
        for key in ("task_sha256", "start_utc", "end_utc", "wall_seconds", "exit_code", "timed_out", "init"):
            self.assertIn(key, meta)
        self.assertEqual(meta["init"]["mcp_servers"], {})

    def test_followups_resume_the_session(self):
        self.task = make_task(self.root, task_id="t-turns", prompt="First, in {DATA_DIR}.",
                              followups=["Second.", "Third, again in {DATA_DIR}."])
        r, run_dir, meta, rec = self.run_arm("native")
        self.assertEqual(meta["status"], "ok", meta.get("invalid_reason"))
        self.assertEqual((meta["turns_planned"], meta["turns_completed"]), (3, 3))
        argv = rec["argv"]  # the last turn's
        self.assertEqual(rec["stdin"], "Third, again in " + str(self.work / run.work_name(meta["run_id"]) / "data") + ".")
        self.assertEqual(argv[argv.index("--resume") + 1], "00000000-0000-4000-8000-000000000001")
        events = [json.loads(l) for l in (run_dir / "stream.jsonl").read_text().splitlines() if l.strip()]
        self.assertEqual(sum(1 for e in events if e.get("type") == "result"), 3)
        self.assertEqual((run_dir / "answers.md").read_text().count(run.TURN_SEPARATOR), 2)
        self.assertEqual((run_dir / "prompt.txt").read_text().count(run.TURN_SEPARATOR), 2)
        u = json.loads((run_dir / "usage.json").read_text())
        self.assertEqual(u["conversation_turns"], 3)
        self.assertAlmostEqual(u["cost_usd"], 3 * 0.024828, places=6)

    def test_a_followup_can_start_a_new_session(self):
        self.task = make_task(self.root, task_id="t-days", prompt="Day one.",
                              followups=["Still day one.", {"prompt": "Day two.", "new_session": True}, "Still day two."])
        r, run_dir, meta, rec = self.run_arm("native")
        self.assertEqual(meta["status"], "ok", meta.get("invalid_reason"))
        self.assertEqual((meta["turns_planned"], meta["turns_completed"]), (4, 4))
        argv = rec["argv"]  # the last turn's: it resumes the second session
        self.assertEqual(argv[argv.index("--resume") + 1], "00000000-0000-4000-8000-000000000002")
        events = [json.loads(l) for l in (run_dir / "stream.jsonl").read_text().splitlines() if l.strip()]
        sessions = [e["session_id"] for e in events if e.get("type") == "result"]
        self.assertEqual(sessions, ["00000000-0000-4000-8000-000000000001"] * 2 + ["00000000-0000-4000-8000-000000000002"] * 2)
        self.assertEqual((run_dir / "prompt.txt").read_text().count(run.TURN_SEPARATOR), 3)
        u = json.loads((run_dir / "usage.json").read_text())
        # Each session reports running totals (1x then 2x the stub's usage): 2x per session.
        self.assertAlmostEqual(u["cost_usd"], 4 * 0.024828, places=6)

    def test_the_agent_sees_only_its_own_processes(self):
        if not run.isolation_prefix():
            self.skipTest("unshare cannot make a PID namespace here")
        r = subprocess.run([*run.isolation_prefix(), "ps", "-e", "-o", "pid="], capture_output=True, text=True)
        pids = [int(p) for p in r.stdout.split()]
        self.assertEqual(pids[0], 1)
        self.assertLess(len(pids), 5, r.stdout)

    def test_arm_extra_env_mcp_and_daemon(self):
        r, run_dir, meta, rec = self.run_arm("stubarm")
        self.assertEqual(meta["status"], "ok", meta.get("invalid_reason"))
        self.assertEqual(set(rec["env"]), BASE_ENV_KEYS | {"CLAUDE_CODE_OAUTH_TOKEN", "STUB_EXTRA"})
        self.assertEqual(meta["extra_env"], {"STUB_EXTRA": "1"})
        self.assertEqual(meta["init"]["mcp_servers"], {"stubsrv": "connected"})
        self.assertTrue(meta["probe_active"])
        self.assertEqual(meta["flags"], [])
        pid = int((self.work / run.work_name(meta["run_id"]) / "home" / "arm.pid").read_text())
        with self.assertRaises(ProcessLookupError):
            os.kill(pid, 0)
        self.assertTrue((run_dir / "arm" / "mcp.json").exists())

    def test_failed_mcp_server_makes_the_run_invalid(self):
        r, run_dir, meta, rec = self.run_arm("stubarm", "mcp_failed")
        self.assertEqual(meta["status"], "invalid")
        self.assertIn("stubsrv", meta["invalid_reason"])

    def test_wrong_model_and_api_error_are_invalid(self):
        _, _, meta, _ = self.run_arm("native", "wrong_model")
        self.assertEqual(meta["status"], "invalid")
        self.assertIn("model", meta["invalid_reason"])
        _, _, meta, _ = self.run_arm("native", "api_error", ["--force"])
        self.assertEqual(meta["status"], "invalid")
        self.assertIn("API error", meta["invalid_reason"])

    def test_timeout_interrupts_the_agent(self):
        _, run_dir, meta, _ = self.run_arm("native", "sleep", ["--timeout-min", "0.03"])
        self.assertEqual(meta["status"], "timeout")
        self.assertTrue(meta["timed_out"])
        self.assertIn('"error_during_execution"', (run_dir / "stream.jsonl").read_text())

    def test_refuses_without_token_unless_stub(self):
        claude, _ = make_claude(self.root, "real", version="2.1.296 (Claude Code)")
        env = {k: v for k, v in self.env.items() if not k.endswith("CLAUDE_OAUTH_TOKEN")
               and k != "CLAUDE_CODE_OAUTH_TOKEN"}
        r = run_harness("run.py", ["--task-file", self.task, "--arm", "native", "--rep", 1, "--fixture",
                                   self.fixture, "--out", self.out, "--work", self.work, "--claude-bin",
                                   claude, "--no-venv", "--no-pg-check"], env)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("BENCH_CLAUDE_OAUTH_TOKEN", r.stderr)


class InitValidationTest(unittest.TestCase):
    INIT = {"type": "system", "subtype": "init", "model": "claude-sonnet-5-5",
            "permissionMode": "bypassPermissions", "tools": ["Bash"],
            "mcp_servers": [{"name": "sobre", "status": "connected"}]}

    def test_connected(self):
        reason, summary = run.validate_init(self.INIT, "claude-sonnet-5-5", ["sobre"])
        self.assertIsNone(reason)
        self.assertEqual(summary["mcp_servers"], {"sobre": "connected"})

    def test_failed_missing_or_unexpected_server(self):
        failed = self.INIT | {"mcp_servers": [{"name": "sobre", "status": "failed"}]}
        self.assertIn("failed", run.validate_init(failed, "claude-sonnet-5-5", ["sobre"])[0])
        self.assertIn("missing", run.validate_init(self.INIT | {"mcp_servers": []}, "claude-sonnet-5-5", ["sobre"])[0])
        self.assertIn("unexpected", run.validate_init(self.INIT, "claude-sonnet-5-5", [])[0])

    def test_model_permission_and_no_init(self):
        self.assertIn("model", run.validate_init(self.INIT, "claude-opus-5-5", ["sobre"])[0])
        self.assertIn("permissionMode", run.validate_init(self.INIT | {"permissionMode": "default"},
                                                          "claude-sonnet-5-5", ["sobre"])[0])
        self.assertIsNotNone(run.validate_init(None, "claude-sonnet-5-5", [])[0])


if __name__ == "__main__":
    unittest.main()
