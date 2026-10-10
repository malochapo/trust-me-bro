"""grade.py: the facts grader (placeholders, must / must_not), graded.json, the tests grader."""

import argparse
import json
import tempfile
import unittest
import unittest.mock
from pathlib import Path

import support  # noqa: F401  (puts harness/ on sys.path)

import common
import grade

PLANTS = {"head": "f" * 40, "plants": {"p4-dedup-window-seconds": "cee1281a20e407568926ebb90fd96234b2c9a755"}}
GRADER = {
    "kind": "facts",
    "must": [
        {"id": "file", "any_of": [r"FILE:\s*`?(src/)?dispatch/signal/service\.py\b"]},
        {"id": "function", "any_of": [r"FUNCTION:\s*`?filter_dedup\b", r"FUNCTION:\s*`?_window_start\b"]},
        {"id": "commit", "any_of": [r"INTRODUCED_BY:\s*`?{plant:p4-dedup-window-seconds:short}"]},
    ],
    "must_not": [{"id": "blames-db", "regex": r"CAUSE:.*database outage"}],
}
GOOD = """Root cause found.
file: src/dispatch/signal/service.py
FUNCTION: `_window_start`
CAUSE: the window is read as seconds
INTRODUCED_BY: cee1281a20e4
"""


class FactsTest(unittest.TestCase):
    plants = PLANTS["plants"]

    def test_pass_case_insensitive_any_of_and_short_sha(self):
        g = grade.grade_facts(GRADER, GOOD, self.plants)
        self.assertTrue(g["pass"])
        self.assertEqual(g["score"], 1.0)
        self.assertEqual([m["matched"] for m in g["details"]["must"]], [True, True, True])

    def test_partial_score(self):
        g = grade.grade_facts(GRADER, GOOD.replace("cee1281a", "deadbeef"), self.plants)
        self.assertFalse(g["pass"])
        self.assertAlmostEqual(g["score"], 2 / 3)

    def test_must_not_fails_the_run(self):
        g = grade.grade_facts(GRADER, GOOD + "CAUSE: a database outage\n", self.plants)
        self.assertFalse(g["pass"])
        self.assertEqual(g["score"], 1.0)

    def test_full_sha_placeholder_and_unknown_plant(self):
        full = r"{plant:p4-dedup-window-seconds}"
        self.assertEqual(grade.resolve_plants(full, self.plants), self.plants["p4-dedup-window-seconds"])
        with self.assertRaises(KeyError):
            grade.resolve_plants("{plant:nope:short}", self.plants)


class GradeRunTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.task_file = self.root / "task.json"
        self.task_file.write_text(json.dumps({"id": "log-x", "prompt": "q", "grader": GRADER}))
        (self.root / "plants.json").write_text(json.dumps(PLANTS))
        self.run_dir = self.root / "log-x__native__r1"
        self.run_dir.mkdir()
        common.write_json(self.run_dir / "meta.json", {
            "run_id": "log-x__native__r1", "arm": "native", "rep": 1, "status": "ok",
            "task_file": str(self.task_file), "task_sha256": common.sha256_file(self.task_file)})
        (self.run_dir / "answer.md").write_text(GOOD)

    def tearDown(self):
        self._tmp.cleanup()

    def args(self, **kw):
        return argparse.Namespace(task_file=None, plants=str(self.root / "plants.json"),
                                  judge_model="claude-sonnet-5-5", claude_bin="claude", **kw)

    def test_writes_graded_json(self):
        g = grade.grade_run(self.run_dir, self.args())
        saved = json.loads((self.run_dir / "graded.json").read_text())
        self.assertEqual(saved["pass"], True)
        self.assertEqual(saved["kind"], "facts")
        self.assertEqual(saved["run_id"], "log-x__native__r1")
        self.assertNotIn("warning", g)

    def test_refuses_invalid_runs(self):
        meta = common.read_json(self.run_dir / "meta.json") | {"status": "invalid"}
        common.write_json(self.run_dir / "meta.json", meta)
        with self.assertRaises(SystemExit):
            grade.grade_run(self.run_dir, self.args())


@unittest.skipUnless(common.postgres_ready(), "the tests grader checks that Postgres is up")
class TestsGraderTest(unittest.TestCase):
    def test_hidden_files_command_and_regression(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            repo, task_dir, run_dir = tmp / "repo", tmp / "task", tmp / "run"
            for d in (repo, task_dir / "hidden" / "tests", run_dir):
                d.mkdir(parents=True)
            (task_dir / "hidden" / "tests" / "test_hidden.py").write_text("print('hidden ran')\n")
            task = {"id": "fix-x", "_dir": str(task_dir), "_file": str(task_dir / "task.json")}
            meta = {"work": {"repo": str(repo), "venv": None}}
            ok = {"command": ["python3", "tests/test_hidden.py"], "regression": ["python3", "-c", "pass"]}
            with unittest.mock.patch.object(common, "LOCK_FILE", tmp / "lock"):
                g = grade.grade_tests(ok, task, run_dir, meta)
                self.assertTrue(g["pass"])
                self.assertEqual(g["details"]["hidden_files"], ["tests/test_hidden.py"])
                self.assertIn("hidden ran", (run_dir / "grade_tests.log").read_text())
                bad = ok | {"regression": ["python3", "-c", "raise SystemExit(1)"]}
                self.assertFalse(grade.grade_tests(bad, task, run_dir, meta)["pass"])


if __name__ == "__main__":
    unittest.main()
