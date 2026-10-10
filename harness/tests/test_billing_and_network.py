"""Per-arm API keys, billing check, network flag, and timeouts scored as failures."""

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import support  # noqa: F401  (puts harness/ on sys.path)

import common
import report
import run


class CredentialsTest(unittest.TestCase):
    def test_arm_key_wins_over_the_token(self):
        env = {"BENCH_KEY_LEANCTX": "sk-ant-api03-x", "BENCH_CLAUDE_OAUTH_TOKEN": "sk-ant-oat01-y"}
        with mock.patch.dict(os.environ, env, clear=True):
            self.assertEqual(common.credentials("lean-ctx"), ({"ANTHROPIC_API_KEY": "sk-ant-api03-x"}, "api_key"))
            self.assertEqual(common.credentials("sobre"),
                             ({"CLAUDE_CODE_OAUTH_TOKEN": "sk-ant-oat01-y"}, "oauth_token"))

    def test_nothing_set(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertEqual(common.credentials("judge"), ({}, None))


class BillingCheckTest(unittest.TestCase):
    def init(self, source):
        return [{"type": "system", "subtype": "init", "model": "claude-sonnet-5-5",
                 "permissionMode": "bypassPermissions", "apiKeySource": source, "mcp_servers": []}]

    def test_api_key_run_billed_elsewhere_is_invalid(self):
        meta = {"auth": "api_key", "timed_out": False}
        status, reason = run.decide_status(meta, self.init("none"), {"subtype": "success"}, "claude-sonnet-5-5", [])
        self.assertEqual(status, "invalid")
        self.assertIn("API key", reason)

    def test_api_key_run_billed_to_the_key_is_ok(self):
        meta = {"auth": "api_key", "timed_out": False}
        status, _ = run.decide_status(meta, self.init("ANTHROPIC_API_KEY"), {"subtype": "success"},
                                      "claude-sonnet-5-5", [])
        self.assertEqual(status, "ok")


class NetworkFlagTest(unittest.TestCase):
    def events(self, *commands):
        return [{"type": "assistant", "message": {"content": [
            {"type": "tool_use", "name": "Bash", "input": {"command": c}} for c in commands]}}]

    def test_flags_fetches_and_urls(self):
        found = run.network_commands(self.events(
            "git clone https://github.com/Netflix/dispatch /tmp/d", "curl -s example.com", "pip install requests"))
        self.assertEqual(len(found), 3)

    def test_ignores_local_work(self):
        self.assertEqual(run.network_commands(self.events(
            "git log -p src/dispatch/signal/service.py", "python -m pytest tests/signal",
            "curl_like_name=1", "echo http://localhost:8000")), [])


class TimeoutScoringTest(unittest.TestCase):
    def test_timeouts_and_errors_count_as_failures_invalid_runs_do_not(self):
        runs = [
            {"meta": {"status": "ok"}, "graded": {"pass": True}, "usage": {}},
            {"meta": {"status": "timeout"}, "graded": None, "usage": {}},
            {"meta": {"status": "error"}, "graded": None, "usage": {}},
            {"meta": {"status": "invalid"}, "graded": None, "usage": {}},
        ]
        scored = report.scored(runs)
        self.assertEqual(len(scored), 3)
        self.assertEqual([report.succeeded(r) for r in scored], [1.0, 0.0, 0.0])


if __name__ == "__main__":
    unittest.main()
