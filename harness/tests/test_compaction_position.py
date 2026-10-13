"""tasks5/make.py and compaction_position.py: where the /compact goes, and how a run is read."""

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

import support  # noqa: F401  (puts harness/ on sys.path)
import compaction_position

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("make_tasks5", ROOT / "tasks5" / "make.py")
make = importlib.util.module_from_spec(spec)
spec.loader.exec_module(make)


class VariantTest(unittest.TestCase):
    TASK = {"id": "long-x", "notes": "n", "followups": ["m2", "m3", "/compact", "m4", "m5", "m6", "m7"]}

    def test_the_compact_moves_and_the_messages_stay(self):
        for position, expected in {0: ["m2", "m3", "m4", "m5", "m6", "m7"],
                                   2: ["m2", "/compact", "m3", "m4", "m5", "m6", "m7"],
                                   3: self.TASK["followups"],
                                   5: ["m2", "m3", "m4", "m5", "/compact", "m6", "m7"]}.items():
            v = make.variant(self.TASK, position)
            self.assertEqual(v["followups"], expected)
            self.assertEqual(v["id"], f"long-x-c{position}")

    def test_the_built_tasks_match_tasks4_but_for_the_compact(self):
        for name in make.TASKS:
            source = json.loads((ROOT / "tasks4" / name / "task.json").read_text())
            for position in make.POSITIONS:
                built = json.loads((ROOT / "tasks5" / f"{name}-c{position}" / "task.json").read_text())
                self.assertEqual(built["grader"], source["grader"])
                self.assertEqual([m for m in built["followups"] if m != "/compact"],
                                 [m for m in source["followups"] if m != "/compact"])


class ReadRunTest(unittest.TestCase):
    def test_split_id(self):
        self.assertEqual(compaction_position.split_id("long-security-then-redaction-c5"),
                         ("long-security-then-redaction", 5))

    def test_scan_counts_requests_compactions_and_the_tier(self):
        events = [
            {"type": "assistant", "message": {"id": "a", "usage": {"input_tokens": 5, "cache_read_input_tokens": 120000}}},
            {"type": "assistant", "message": {"id": "a", "usage": {"input_tokens": 5, "cache_read_input_tokens": 120000}}},
            {"type": "assistant", "parent_tool_use_id": "t", "message": {"id": "s", "usage": {"input_tokens": 200000}}},
            {"type": "system", "subtype": "compact_boundary",
             "compact_metadata": {"trigger": "manual", "pre_tokens": 120005, "post_tokens": 6000}},
            {"type": "assistant", "message": {"id": "b", "usage": {"input_tokens": 3, "cache_creation_input_tokens": 6000}}},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "stream.jsonl").write_text("\n".join(json.dumps(e) for e in events) + "\nnot json\n")
            got = compaction_position.scan(Path(tmp))
        self.assertEqual(got, {"requests": 2, "max_prompt": 120005, "over_tier": 1,
                               "compactions": [("manual", 120005, 6000)]})

    def test_facts_split_by_half(self):
        graded = {"details": {"parts": [{"kind": "tests", "pass": True}, {"kind": "facts", "details": {
            "must": [{"id": "file", "matched": True}, {"id": "canary", "matched": False}],
            "must_not": [{"id": "x", "matched": True}]}}]}}
        self.assertEqual(compaction_position.facts(graded, "long-incident-then-dedup"), (1, 1, 0, 1, 1))
        self.assertTrue(compaction_position.tests_pass(graded))


if __name__ == "__main__":
    unittest.main()
