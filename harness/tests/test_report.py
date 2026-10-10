"""report.py: per-arm summaries, paired bootstrap (deterministic), verdicts, outputs."""

import argparse
import math
import tempfile
import unittest
from pathlib import Path

import support  # noqa: F401  (puts harness/ on sys.path)

import common
import report

# task -> (native passes over 2 reps, native cost, sobre passes, sobre cost)
DATA = {
    "t1": ([1, 1], 1.00, [1, 1], 0.50),
    "t2": ([1, 0], 2.00, [1, 1], 1.00),
    "t3": ([0, 0], 1.00, [0, 1], 2.00),
    "t4": ([1, 1], 4.00, [1, 0], 1.00),
}


def write_run(raw, task, arm, rep, passed, cost, status="ok", flags=()):
    run_id = f"{task}__{arm}__r{rep}"
    d = raw / run_id
    d.mkdir(parents=True)
    common.write_json(d / "meta.json", {"run_id": run_id, "task_id": task, "arm": arm, "rep": rep,
                                        "status": status, "flags": list(flags), "wall_seconds": 60.0,
                                        "invalid_reason": "boom" if status == "invalid" else None})
    if status == "ok":
        common.write_json(d / "graded.json", {"pass": bool(passed), "score": float(passed)})
        common.write_json(d / "usage.json", {"cost_usd": cost, "client_total_cost_usd": cost, "num_turns": 10,
                                             "tokens": {"input": 1, "output": 2, "cache_read": 3,
                                                        "cache_write_5m": 4, "cache_write_1h": 5}})


class ReportTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.raw = Path(self._tmp.name) / "raw"
        for task, (n_pass, n_cost, s_pass, s_cost) in DATA.items():
            for rep in (1, 2):
                write_run(self.raw, task, "native", rep, n_pass[rep - 1], n_cost)
                write_run(self.raw, task, "sobre", rep, s_pass[rep - 1], s_cost)
        write_run(self.raw, "t1", "sobre", 3, 0, 0, status="invalid")
        write_run(self.raw, "t2", "sobre", 3, 1, 0.1, flags=["probe_inactive"])

    def tearDown(self):
        self._tmp.cleanup()

    def test_point_estimates(self):
        runs, good, arms, summaries, table, comps = report.build(self.raw, resamples=200, seed=1)
        self.assertEqual(arms, ["native", "sobre"])
        self.assertEqual(summaries["native"]["n"], 8)
        self.assertEqual(summaries["sobre"]["n"], 9)  # the invalid run does not count
        self.assertAlmostEqual(summaries["native"]["success_rate"], 5 / 8)
        c = comps["sobre"]
        self.assertEqual(c["tasks_paired"], 4)
        # per-task success: native 1, .5, 0, 1; sobre 1, 1 (3 ok reps on t2), .5, .5
        self.assertAlmostEqual(c["delta_success_pp"], 100 * (0 + .5 + .5 - .5) / 4)
        t2_cost = (1.0 + 1.0 + 0.1) / 3
        ratios = [0.5, t2_cost / 2.0, 2.0, 0.25]
        self.assertAlmostEqual(c["cost_ratio_geo"], math.exp(sum(map(math.log, ratios)) / 4))
        self.assertLessEqual(c["delta_ci_low"], c["delta_success_pp"])
        self.assertGreaterEqual(c["delta_ci_high"], c["delta_success_pp"])
        self.assertLessEqual(c["ratio_ci_low"], c["ratio_ci_high"])

    def test_bootstrap_is_deterministic(self):
        a = report.build(self.raw, resamples=2000, seed=7)[-1]["sobre"]
        b = report.build(self.raw, resamples=2000, seed=7)[-1]["sobre"]
        self.assertEqual(a, b)
        pairs = [((i * 7) % 5 / 4, (i * 3) % 4 / 3, 0.5 + (i * 11) % 13 / 10) for i in range(30)]
        self.assertEqual(report.bootstrap(pairs, 1000, 7), report.bootstrap(pairs, 1000, 7))
        self.assertNotEqual(report.bootstrap(pairs, 1000, 7), report.bootstrap(pairs, 1000, 8))

    def test_verdicts(self):
        pairs = [(1.0, 1.0, 1.0)] * 10
        self.assertEqual(report.bootstrap(pairs, 100, 1)[0], (0.0, 0.0))
        comps = report.build(self.raw, resamples=500, seed=1, margin_pp=1000)[-1]
        self.assertEqual(comps["sobre"]["verdict"], "non-inferior")

    def test_outputs_list_invalid_and_flagged_runs(self):
        out = Path(self._tmp.name) / "out"
        report.main(["--raw", str(self.raw), "--out", str(out), "--resamples", "100"])
        md = (out / "report.md").read_text()
        self.assertIn("t1__sobre__r3 | invalid | boom", md)
        self.assertIn("t2__sobre__r3 | ok, flagged | probe_inactive", md)
        rows = (out / "report.csv").read_text().splitlines()
        self.assertEqual(len(rows), 3)
        self.assertTrue(rows[0].startswith("arm,n,success_rate"))


class BenchScheduleTest(unittest.TestCase):
    def test_arms_interleaved_per_task_in_seeded_order(self):
        import bench
        arms = ["native", "sobre", "rtk"]
        plan = bench.schedule(["a", "b"], arms, 2, seed=3)
        self.assertEqual(plan, bench.schedule(["a", "b"], arms, 2, seed=3))
        self.assertEqual(len(plan), 12)
        for i in range(0, 12, 3):
            block = plan[i:i + 3]
            self.assertEqual({arm for _, arm, _ in block}, set(arms))
            self.assertEqual(len({(t, r) for t, _, r in block}), 1)
        orders = {tuple(arm for _, arm, _ in plan[i:i + 3]) for i in range(0, 12, 3)}
        self.assertGreater(len(orders), 1)


if __name__ == "__main__":
    unittest.main()
