"""clear_sim.py: recorded cost with no policy, and what a clearing saves and costs."""

import unittest

import support  # noqa: F401  (puts harness/ on sys.path)

import clear_sim

FLAT = clear_sim.unit_prices(None, "1h")  # not in the price table: read 0.1, write 2, input 1 per token


def call(read, write, results=(), output=0, segment=1):
    return {"usage": {"cache_read_input_tokens": read, "cache_creation_input_tokens": write,
                      "input_tokens": 0, "output_tokens": output},
            "segment": segment, "results": list(results)}


class ClearSimTest(unittest.TestCase):
    def test_no_policy_prices_the_recorded_tokens(self):
        calls = [call(0, 1000), call(1000, 500, [1000])]
        self.assertAlmostEqual(clear_sim.input_cost(calls, FLAT, 1.0), 1000 * 2 + 1000 * 0.1 + 500 * 2)

    def test_clearing_a_big_old_result_pays_off_over_later_calls(self):
        # a 20,000-token result early, then 30 calls that each add a small one
        calls = [call(0, 5000), call(5000, 20000, [20000])]
        prompt = 25000
        for _ in range(30):
            calls.append(call(prompt, 200, [200]))
            prompt += 200
        recorded = clear_sim.input_cost(calls, FLAT, 1.0)
        cleared = clear_sim.input_cost(calls, FLAT, 1.0, (20000, 3, 5000))
        # the result's first write stays; the 30 later reads of it go
        self.assertLess(cleared, 0.7 * recorded)

    def test_clearing_near_the_end_costs_more_than_it_saves(self):
        # a small old result with 20,000 tokens of conversation after it, cleared one call before the
        # end: everything after it is written again, for one cheaper read
        calls = ([call(0, 5000), call(5000, 2000, [2000]), call(7000, 20000)]
                 + [call(27000 + 200 * i, 200, [200]) for i in range(4)])
        recorded = clear_sim.input_cost(calls, FLAT, 1.0)
        self.assertGreater(clear_sim.input_cost(calls, FLAT, 1.0, (27500, 3, 1000)), recorded)

    def test_the_cap_bounds_a_result_after_a_cache_miss(self):
        # a cache miss rewrites the whole prompt: without the cap all of it would count as the result
        miss = [call(0, 5000), call(0, 30000, [1000])] + [call(30000, 100, [100]) for _ in range(20)]
        capped = clear_sim.input_cost(miss, FLAT, 0.5, (10000, 3, 0))
        uncapped = clear_sim.input_cost(miss, FLAT, 100.0, (10000, 3, 0))
        self.assertLess(uncapped, capped)


if __name__ == "__main__":
    unittest.main()
