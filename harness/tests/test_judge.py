"""judge.py: redaction, a prompt that never names the arm, the call to claude."""

import json
import os
import tempfile
import unittest
from pathlib import Path

from support import make_claude

import judge

TASK = {"id": "qa-x", "prompt": "Where is X configured? Logs in {DATA_DIR}.",
        "grader": {"kind": "judge", "reference": "In config.py, SETTING_X.", "rubric": "3: exact. 0: wrong."}}
ANSWER = ("I used mcp__sobre__sobre_read and sobre_search, then lean-ctx, lean_ctx, LeanCTX and "
          "ctx_read; Headroom and RTK said <<ccr:abc123>>. [sobre: compressed] It is in config.py.")


class JudgeTest(unittest.TestCase):
    def test_redaction(self):
        red = judge.redact(ANSWER)
        for word in ("sobre", "lean", "ctx", "headroom", "rtk", "mcp__", "ccr"):
            self.assertNotIn(word, red.lower())
        self.assertIn("It is in config.py.", red)

    def test_prompt_has_question_reference_rubric_and_no_placeholder(self):
        prompt = judge.build_prompt(TASK, ANSWER)
        self.assertIn("Where is X configured?", prompt)
        self.assertIn("In config.py, SETTING_X.", prompt)
        self.assertIn("3: exact. 0: wrong.", prompt)
        self.assertNotIn("{DATA_DIR}", prompt)
        self.assertNotIn("sobre", prompt.lower())

    def test_judge_run_with_stub(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            claude, record = make_claude(tmp, "judge")
            run_dir = tmp / "qa-x__sobre__r1"  # the arm is in the run dir's name, never in what the judge sees
            run_dir.mkdir()
            (run_dir / "answer.md").write_text(ANSWER)
            os.environ["CLAUDE_CODE_OAUTH_TOKEN_TEST_LEAK"] = "leak"
            try:
                verdict = judge.judge_run(run_dir, TASK, "claude-sonnet-5-5", str(claude))
            finally:
                del os.environ["CLAUDE_CODE_OAUTH_TOKEN_TEST_LEAK"]
            self.assertEqual(verdict["score"], 2)
            rec = json.loads(record.read_text())
            self.assertNotIn("sobre", rec["cwd"])
            self.assertNotIn("sobre", rec["stdin"].lower())
            self.assertEqual(rec["stdin"], (run_dir / "judge_prompt.txt").read_text())
            self.assertTrue(set(rec["env"]) <= {"PATH", "HOME", "CLAUDE_CONFIG_DIR", "LANG", "TERM", "IS_SANDBOX",
                                                "DISABLE_AUTOUPDATER", "CLAUDE_CODE_OAUTH_TOKEN"})
            argv = rec["argv"]
            self.assertEqual(argv[argv.index("--tools") + 1], "")
            self.assertEqual(argv[argv.index("--output-format") + 1], "json")
            schema = json.loads(argv[argv.index("--json-schema") + 1])
            self.assertEqual(schema["properties"]["score"]["maximum"], 3)
            self.assertTrue((run_dir / "judge_reply.json").exists())


if __name__ == "__main__":
    unittest.main()
