"""leakage.py: fact tasks asked with no code and no tools, graded like a run."""

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from support import make_claude, make_task

import leakage


class LeakageTest(unittest.TestCase):
    def check(self, scenario):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            claude, record = make_claude(tmp, scenario)
            make_task(tmp, "qa-x", data=False)
            tasks = tmp / "tasks"
            plants = tmp / "plants.json"
            plants.write_text(json.dumps({"plants": {}}))
            env = {"BENCH_KEY_JUDGE": "sk-ant-api03-judge", "ANTHROPIC_BASE_URL": "http://leak", "CLAUDE_X": "1"}
            with mock.patch.dict(os.environ, env, clear=True):
                code = leakage.main(["--tasks", str(tasks / "*" / "task.json"), "--reps", "2",
                                     "--plants", str(plants), "--out", str(tmp / "out"), "--claude-bin", str(claude)])
            seen = json.loads(record.read_text())
            summary = json.loads((tmp / "out" / "summary.json").read_text())
            return code, seen, summary

    def test_a_task_answered_from_memory_is_reported(self):
        code, _, summary = self.check("leak")
        self.assertEqual(code, 1)
        self.assertEqual(summary["leaked"], ["qa-x"])

    def test_no_code_no_tools_no_leaked_env(self):
        code, seen, summary = self.check("judge")
        self.assertEqual((code, summary["leaked"]), (0, []))
        argv = seen["argv"]
        self.assertEqual(argv[argv.index("--tools") + 1], "")
        self.assertIn("You cannot see the repository", seen["stdin"])
        self.assertRegex(seen["cwd"], r"/leakage-[^/]+/work$")  # a fresh empty dir, removed afterwards
        self.assertEqual(seen["env"].get("ANTHROPIC_API_KEY"), "sk-ant-api03-judge")
        leaked = [k for k in seen["env"] if k.startswith(("CLAUDE_X", "ANTHROPIC_BASE"))]
        self.assertEqual(leaked, [])


if __name__ == "__main__":
    unittest.main()
