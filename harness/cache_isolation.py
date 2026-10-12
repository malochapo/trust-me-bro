#!/usr/bin/env python3
"""How much each pilot's cost ratios owed to the shared prompt cache (docs/cache-isolation.md).

Every API key of a workspace shares its prompt cache, and a session's first request starts
with Claude Code's tool definitions and system prompt: the same prefix in every run of a
setup. An arm that keeps native's prefix finds it written by the runs before it; one that
changes it (tools loaded up front, a proxy that rewrites the prompt) more often starts cold.

Per pilot, this prints how often each arm's sessions started warm, then each arm's cost ratio
to native three ways, from the same runs:
  measured  each run's billed tokens, as recorded;
  cold      every session started on a cold cache (usage.cold_start);
  warm      every session started on a warm one: the arm's prefix (the most common non-zero
            first read of its sessions) read instead of written where a start missed it.
Cold and warm bracket the cache state a user of either setup would meet; the gap between them
and measured is what the interleaving put into the published ratios.

Usage: python3 -I harness/cache_isolation.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # -I leaves the script dir off sys.path

import json
import math
import random
import statistics
from collections import Counter, defaultdict

import common
import report
import usage

# (label, raw dir, what the pilot's report bootstraps over)
PILOTS = [("pilot 1, Sonnet", "results/raw", "tasks"), ("pilot 2, Sonnet", "results/pilot2/raw", "tasks"),
          ("pilot 3, Haiku", "results/pilot3/haiku/raw", "tasks"), ("pilot 3, Sonnet", "results/pilot3/sonnet/raw", "tasks"),
          ("pilot 4, Haiku", "results/pilot4/haiku/raw", "tasks"), ("pilot 4, Sonnet", "results/pilot4/sonnet/raw", "tasks"),
          ("pilot 5, Haiku", "results/pilot5/haiku/raw", "runs"), ("pilot 5, Sonnet", "results/pilot5/sonnet/raw", "runs")]
SEED = 20261010


def load(raw_dir, prices):
    """Scored runs, each with its session starts and its three costs."""
    runs = report.scored(report.load_runs(raw_dir))
    for r in runs:
        stream = Path(raw_dir) / r["meta"]["run_id"] / "stream.jsonl"
        r["starts"] = usage.session_starts(usage.read_events(stream)) if stream.exists() else []
    prefix = {}
    for arm in {r["meta"]["arm"] for r in runs}:
        reads = Counter(u.get("cache_read_input_tokens") or 0 for r in runs if r["meta"]["arm"] == arm for _, u in r["starts"])
        reads.pop(0, None)
        prefix[arm] = reads.most_common(1)[0][0] if reads else 0
    for r in runs:
        r["cost"], r["warm"] = r["usage"].get("cost_usd"), r["usage"].get("cost_usd")
        for model, u in r["starts"]:
            missed = prefix[r["meta"]["arm"]] - (u.get("cache_read_input_tokens") or 0)
            _, price = usage.price_for(model, prices["models"])
            if missed > 0 and price and r["warm"] is not None:
                r["warm"] -= missed * (price["cache_write_5m"] - price["cache_read"]) / 1e6
    return runs, prefix


def ratio_over_tasks(runs, arm, key):
    """The geometric mean of per-task ratios of means, with report.py's bootstrap over tasks."""
    table = defaultdict(dict)
    groups = defaultdict(list)
    for r in runs:
        groups[(r["meta"]["arm"], r["meta"]["task_id"])].append(r)
    for (a, task), rs in groups.items():
        values = [r[key] for r in rs]
        table[a][task] = (0.0, None if None in values else statistics.mean(values))
    c = report.compare(table, arm, 10_000, SEED, 5.0)
    return (c["cost_ratio_geo"], c["ratio_ci_low"], c["ratio_ci_high"]) if c and c["cost_ratio_geo"] else None


def ratio_over_runs(runs, arm, key, resamples=4000):
    """The same point estimate, with pilot 5's bootstrap over runs within each task."""
    by = defaultdict(list)
    for r in runs:
        by[(r["meta"]["arm"], r["meta"]["task_id"])].append(r[key])
    tasks = sorted(t for a, t in by if a == arm and (report.BASELINE, t) in by)
    if not tasks or any(None in by[(a, t)] for t in tasks for a in (arm, report.BASELINE)):
        return None
    log_ratio = lambda pick: statistics.mean(math.log(statistics.mean(pick(by[(arm, t)])) / statistics.mean(pick(by[(report.BASELINE, t)])))
                                             for t in tasks)
    rng = random.Random(SEED)
    boots = sorted(math.exp(log_ratio(lambda xs: [rng.choice(xs) for _ in xs])) for _ in range(resamples))
    return math.exp(log_ratio(lambda xs: xs)), boots[int(0.025 * resamples)], boots[int(0.975 * resamples) - 1]


def fmt(r):
    return "-" if r is None else f"{r[0]:.2f} ({r[1]:.2f}–{r[2]:.2f})"


def main():
    prices = json.loads(usage.DEFAULT_PRICES.read_text())
    print("## Sessions that started on a warm cache\n")
    print("| pilot | arm | sessions | started warm | prefix read when warm (tokens) |")
    print("|---|---|---|---|---|")
    results = []
    for label, raw, over in PILOTS:
        runs, prefix = load(common.BENCH_ROOT / raw, prices)
        arms = report.arm_order({r["meta"]["arm"] for r in runs})
        for arm in arms:
            starts = [u for r in runs if r["meta"]["arm"] == arm for _, u in r["starts"]]
            warm = sum(1 for u in starts if u.get("cache_read_input_tokens"))
            print(f"| {label} | {arm} | {len(starts)} | {warm} ({100 * warm / len(starts):.0f}%) | {prefix[arm]:,} |")
        results.append((label, over, runs, arms))
    print("\n## Cost ratio to native: measured, every session cold, every session warm\n")
    print("| pilot | arm | bootstrap over | measured | cold | warm |")
    print("|---|---|---|---|---|---|")
    for label, over, runs, arms in results:
        ratio = ratio_over_tasks if over == "tasks" else ratio_over_runs
        for arm in arms:
            if arm == report.BASELINE:
                continue
            for r in runs:
                r["cold"] = r["cost_cold"]
            print(f"| {label} | {arm} | {over} | {fmt(ratio(runs, arm, 'cost'))} | {fmt(ratio(runs, arm, 'cold'))} | "
                  f"{fmt(ratio(runs, arm, 'warm'))} |")


if __name__ == "__main__":
    main()
