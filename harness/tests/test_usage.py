"""usage.py: token classes, the 5m/1h split, deduplication, cost arithmetic, tool stats."""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from support import FAKE

import usage


def fake_stream(tmp):
    """The stub's transcript, as run.py would capture it."""
    out = subprocess.run([sys.executable, "-I", str(FAKE), "-p", "x", "--model", "claude-sonnet-5-5",
                          "--output-format", "stream-json"], cwd=tmp, stdin=subprocess.DEVNULL,
                         capture_output=True, text=True, check=True)
    path = Path(tmp) / "stream.jsonl"
    path.write_text(out.stdout)
    return path


def write_stream(tmp, events):
    path = Path(tmp) / "stream.jsonl"
    path.write_text("\n".join(json.dumps(e) for e in events) + "\nnot json\n")
    return path


class UsageTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = self._tmp.name

    def tearDown(self):
        self._tmp.cleanup()

    def test_tokens_split_and_cost(self):
        u = usage.compute(fake_stream(self.tmp))
        self.assertEqual(u["source"], "modelUsage")
        sonnet = u["by_model"]["claude-sonnet-5-5"]
        # modelUsage: 4500 cache writes; messages msg_1 (0/3000) + msg_2 (500/1000), msg_1 counted once.
        self.assertEqual((sonnet["cache_write_5m"], sonnet["cache_write_1h"]), (500, 4000))
        self.assertEqual((sonnet["input"], sonnet["output"], sonnet["cache_read"]), (14, 700, 5000))
        # 14*2 + 700*10 + 5000*0.1 + 500*2.5 + 4000*4 = 24778 -> $0.024778
        self.assertAlmostEqual(sonnet["cost_usd"], 0.024778, places=9)
        haiku = u["by_model"]["claude-haiku-5-5"]
        self.assertEqual((haiku["cache_write_5m"], haiku["cache_write_1h"]), (200, 0))
        # 50*0.1 + 40*0.5 + 200*0.125 = 50 -> $0.00005
        self.assertAlmostEqual(haiku["cost_usd"], 0.00005, places=9)
        self.assertAlmostEqual(u["cost_usd"], 0.024828, places=9)
        self.assertEqual(u["tokens"], {"input": 64, "output": 740, "cache_read": 5000,
                                       "cache_write_5m": 700, "cache_write_1h": 4000})
        self.assertEqual(u["client_total_cost_usd"], 0.0301)
        self.assertEqual((u["num_turns"], u["duration_ms"]), (3, 12345))
        self.assertEqual(u["flags"], [])

    def test_resumed_turns_report_running_totals_and_long_prompts_are_priced(self):
        """Two resumed turns, each with its result event; one Haiku request over 100K tokens.
        The second result event's modelUsage and total_cost_usd include the first turn's."""
        def assistant(msg_id, inp, read, write):
            return {"type": "assistant", "message": {
                "id": msg_id, "model": "claude-haiku-5-5", "content": [],
                "usage": {"input_tokens": inp, "output_tokens": 1, "cache_read_input_tokens": read,
                          "cache_creation_input_tokens": write,
                          "cache_creation": {"ephemeral_5m_input_tokens": write, "ephemeral_1h_input_tokens": 0}}}}

        def result(inp, out, read, write, cost):
            return {"type": "result", "subtype": "success", "num_turns": 1, "duration_ms": 10,
                    "total_cost_usd": cost, "modelUsage": {"claude-haiku-5-5": {
                        "inputTokens": inp, "outputTokens": out, "cacheReadInputTokens": read,
                        "cacheCreationInputTokens": write, "costUSD": cost}}}

        events = [assistant("m1", 10, 50_000, 1_000), result(10, 100, 50_000, 1_000, 0.01),
                  assistant("m2", 10, 120_000, 1_000), result(20, 200, 170_000, 2_000, 0.03)]
        path = Path(self.tmp) / "stream.jsonl"
        path.write_text("".join(json.dumps(e) + "\n" for e in events))
        u = usage.compute(path)
        haiku = u["by_model"]["claude-haiku-5-5"]
        self.assertEqual((haiku["input"], haiku["output"], haiku["cache_read"], haiku["cache_write_5m"]),
                         (20, 200, 170_000, 2_000))
        self.assertEqual(u["conversation_turns"], 2)
        self.assertAlmostEqual(u["client_total_cost_usd"], 0.03)
        self.assertEqual(u["num_turns"], 2)
        # m2's prompt (131,010 tokens) is over 100K: its tokens, and half the output (1 of 2
        # requests), take the long-prompt prices.
        expected = (10 * 0.10 + 10 * 0.50            # input
                    + 100 * 0.50 + 100 * 2.50        # output
                    + 50_000 * 0.01 + 120_000 * 0.05  # cache read
                    + 1_000 * 0.125 + 1_000 * 0.625) / 1e6
        self.assertAlmostEqual(haiku["cost_usd"], expected, places=12)

    def test_a_count_that_starts_again_adds_to_the_one_before(self):
        def result(out, cost, api_ms):
            return {"type": "result", "subtype": "success", "num_turns": 2, "duration_ms": 5,
                    "duration_api_ms": api_ms, "total_cost_usd": cost, "modelUsage": {"claude-sonnet-5-5": {
                        "inputTokens": api_ms, "outputTokens": out, "cacheReadInputTokens": 0,
                        "cacheCreationInputTokens": 0, "costUSD": cost}}}

        # Running totals 100, 300, then a session that started again at 50, then 80.
        events = [result(100, 0.001, 10), result(300, 0.003, 30), result(50, 0.0005, 5), result(80, 0.0008, 8)]
        u = usage.compute(write_stream(self.tmp, events))
        self.assertEqual(u["by_model"]["claude-sonnet-5-5"]["output"], 380)
        self.assertEqual(u["by_model"]["claude-sonnet-5-5"]["input"], 38)
        self.assertAlmostEqual(u["client_total_cost_usd"], 0.0038)
        self.assertEqual(u["duration_api_ms"], 38)
        self.assertEqual((u["num_turns"], u["duration_ms"]), (8, 20))

    def test_a_new_session_adds_its_own_running_totals(self):
        def result(session, out, cost):
            return {"type": "result", "subtype": "success", "session_id": session, "num_turns": 1,
                    "duration_ms": 5, "duration_api_ms": out, "total_cost_usd": cost, "modelUsage": {
                        "claude-sonnet-5-5": {"inputTokens": 1, "outputTokens": out, "cacheReadInputTokens": 0,
                                              "cacheCreationInputTokens": 0, "costUSD": cost}}}

        # Session a: 100 then 300 in all. Session b, new: 500 (more than a's total), then 600.
        events = [result("a", 100, 0.001), result("a", 300, 0.003), result("b", 500, 0.005), result("b", 600, 0.006)]
        u = usage.compute(write_stream(self.tmp, events))
        self.assertEqual(u["by_model"]["claude-sonnet-5-5"]["output"], 900)
        self.assertEqual(u["by_model"]["claude-sonnet-5-5"]["input"], 2)
        self.assertAlmostEqual(u["client_total_cost_usd"], 0.009)
        self.assertEqual(u["duration_api_ms"], 900)

    def test_tool_stats(self):
        u = usage.compute(fake_stream(self.tmp))
        self.assertEqual(u["tool_calls"], {"Agent": 1, "Bash": 1, "Grep": 1, "Read": 1})
        self.assertEqual(u["tool_calls_total"], 4)
        self.assertEqual(u["tool_results"], 4)
        self.assertEqual(u["tool_result_errors"], 1)
        self.assertEqual(u["tool_result_chars"], len("commit abc\n") + 100 + len("a.py:1:def f") + len("found it"))

    def test_without_split_writes_count_as_1h_and_are_flagged(self):
        msg = {"type": "assistant", "parent_tool_use_id": None,
               "message": {"id": "m1", "model": "claude-sonnet-5-5", "content": [{"type": "text", "text": "hi"}],
                           "usage": {"input_tokens": 1, "output_tokens": 1, "cache_read_input_tokens": 0,
                                     "cache_creation_input_tokens": 1000}}}
        result = {"type": "result", "subtype": "success", "is_error": False, "result": "hi", "num_turns": 1,
                  "total_cost_usd": 0.01, "modelUsage": {"claude-sonnet-5-5": {
                      "inputTokens": 1, "outputTokens": 1, "cacheReadInputTokens": 0,
                      "cacheCreationInputTokens": 1000, "costUSD": 0.01}}}
        u = usage.compute(write_stream(self.tmp, [msg, msg, result]))
        sonnet = u["by_model"]["claude-sonnet-5-5"]
        self.assertEqual((sonnet["cache_write_5m"], sonnet["cache_write_1h"]), (0, 1000))
        self.assertIn("cache_write_split_assumed_1h:claude-sonnet-5-5", u["flags"])
        self.assertAlmostEqual(u["cost_usd"], (1 * 2 + 1 * 10 + 1000 * 4) / 1e6, places=12)

    def test_without_result_falls_back_to_messages(self):
        msg = {"type": "assistant", "parent_tool_use_id": None,
               "message": {"id": "m1", "model": "claude-sonnet-5-5-20261001", "content": [],
                           "usage": {"input_tokens": 3, "output_tokens": 2, "cache_read_input_tokens": 7,
                                     "cache_creation_input_tokens": 10,
                                     "cache_creation": {"ephemeral_5m_input_tokens": 10}}}}
        u = usage.compute(write_stream(self.tmp, [msg, msg]))
        self.assertEqual(u["source"], "messages")
        m = u["by_model"]["claude-sonnet-5-5-20261001"]
        self.assertEqual(m["price_key"], "claude-sonnet-5-5")  # dated id priced by prefix
        self.assertEqual((m["input"], m["cache_read"], m["cache_write_5m"]), (3, 7, 10))
        self.assertIn("no_result_event", u["flags"])

    def test_unknown_model_is_flagged(self):
        result = {"type": "result", "subtype": "success", "modelUsage": {"mystery-1": {"inputTokens": 5}}}
        u = usage.compute(write_stream(self.tmp, [result]))
        self.assertIn("unpriced_model:mystery-1", u["flags"])
        self.assertIsNone(u["by_model"]["mystery-1"]["cost_usd"])


if __name__ == "__main__":
    unittest.main()


class ColdStartTest(unittest.TestCase):
    """cold_start: each session's first response, and each subagent type's first, priced cold."""

    PRICES = json.loads(usage.DEFAULT_PRICES.read_text())

    @staticmethod
    def assistant(msg_id, read, session="a", parent=None, model="claude-sonnet-5-5", w5=100, w1=0, content=()):
        return {"type": "assistant", "session_id": session, "parent_tool_use_id": parent, "message": {
            "id": msg_id, "model": model, "content": list(content),
            "usage": {"input_tokens": 1, "output_tokens": 1, "cache_read_input_tokens": read,
                      "cache_creation_input_tokens": w5 + w1,
                      "cache_creation": {"ephemeral_5m_input_tokens": w5, "ephemeral_1h_input_tokens": w1}}}}

    @staticmethod
    def spawn(tool_id, kind=None):
        return {"type": "tool_use", "id": tool_id, "name": "Agent",
                "input": {"prompt": "look", **({"subagent_type": kind} if kind else {})}}

    def test_starts_are_priced_cold_and_the_rest_left_alone(self):
        events = [
            self.assistant("m1", 10_000, content=[self.spawn("t1", "Explore"), self.spawn("t2", "Explore"),
                                                  self.spawn("t3", "fork")]),
            self.assistant("m1", 10_000),                     # the same response again: counted once
            self.assistant("m2", 15_000),                     # a later call of session a: its own cache
            self.assistant("s1", 3_000, parent="t1"),         # the first Explore: a start
            self.assistant("s2", 9_000, parent="t1"),         # its second call
            self.assistant("s3", 4_000, parent="t2"),         # a second Explore: finds what the first wrote
            self.assistant("f1", 20_000, parent="t3"),        # a fork reads its parent's context
            self.assistant("m3", 12_000, session="b", w5=0, w1=300),  # a new session, 1-hour writes only
            self.assistant("x1", 50_000, session="c", model="<synthetic>"),
        ]
        cold = usage.cold_start(events, self.PRICES)
        self.assertEqual(cold["starts"], 3)
        self.assertEqual(cold["cache_read_tokens"], 10_000 + 3_000 + 12_000)
        # Sonnet 5.5: a cache read costs $0.10/M, a 5-minute write $2.50/M, a 1-hour write $4.00/M.
        expected = (10_000 * 2.4 + 3_000 * 2.4 + 12_000 * 3.9) / 1e6
        self.assertAlmostEqual(cold["extra_usd"], expected, places=9)
        self.assertEqual(cold["unpriced_models"], [])

    def test_a_start_over_the_long_prompt_threshold_takes_the_long_prices(self):
        events = [self.assistant("m1", 120_000, model="claude-haiku-5-5")]
        # Haiku 5.5 over 100K tokens of prompt: a cache read costs $0.05/M, a 5-minute write $0.625/M.
        self.assertAlmostEqual(usage.cold_start(events, self.PRICES)["extra_usd"], 120_000 * 0.575 / 1e6, places=9)

    def test_compute_and_cold_cost(self):
        with tempfile.TemporaryDirectory() as tmp:
            u = usage.compute(fake_stream(tmp))
            self.assertAlmostEqual(u["cost_cold_usd"], u["cost_usd"] + u["cold_start"]["extra_usd"], places=6)
            self.assertGreaterEqual(u["cost_cold_usd"], u["cost_usd"])
            # A run recorded before the field existed: computed from its stream.
            legacy = {k: v for k, v in u.items() if k not in ("cost_cold_usd", "cold_start")}
            self.assertEqual(usage.cold_cost(tmp, legacy), u["cost_cold_usd"])
            self.assertIsNone(usage.cold_cost(Path(tmp) / "missing", legacy))
