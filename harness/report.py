#!/usr/bin/env python3
"""Summarizes graded runs: results/report.md and results/report.csv.

Runs with status "ok" and a graded.json count, and so do timed-out and errored runs,
as failures: running out of time or crashing is the arm's outcome. Invalid runs
(infrastructure: setup, MCP connection, API errors, wrong billing) are never scored. Per arm: runs, success rate, cost
(mean, median), mean tokens per class, turns and wall time. Each arm is then paired
with native task by task (each task's mean over its reps), and 10,000 bootstrap
resamples over tasks, with a fixed seed, give 95% intervals for the difference in
success rate (percentage points) and for the cost ratio (geometric mean of per-task
ratios). Non-inferiority on success: the lower bound of the interval for the
difference must lie above -margin. Invalid, timed-out, errored and flagged runs are
listed at the end.

Cost is given twice. Measured: the run's own tokens. Cold start: the same run had each of its
sessions started with a cold prompt cache (usage.cold_start). Interleaved arms share the
cache of their workspace, so an arm that keeps native's prompt prefix starts warm more often
than one that changes it; the cold-start ratio removes that difference (docs/cache-isolation.md).

Usage: python3 -I harness/report.py [--raw results/raw] [--out results] [--margin-pp 5]
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # -I leaves the script dir off sys.path

import argparse
import csv
import math
import random
import statistics
from collections import defaultdict

import common
import usage
from usage import TOKEN_CLASSES

BASELINE = "native"


def load_runs(raw_dir):
    runs = []
    for meta_path in sorted(Path(raw_dir).glob("*/meta.json")):
        meta = common.read_json(meta_path)
        run_dir = meta_path.parent
        run_usage = common.read_json(run_dir / "usage.json", {}) or {}
        runs.append({"meta": meta, "graded": common.read_json(run_dir / "graded.json"), "usage": run_usage,
                     "cost_cold": usage.cold_cost(run_dir, run_usage)})
    return runs


def scored(runs):
    return [r for r in runs if r["meta"].get("status") in ("timeout", "error")
            or (r["meta"].get("status") == "ok" and r["graded"] and r["graded"].get("pass") is not None)]


def succeeded(r):
    return 1.0 if r["meta"].get("status") == "ok" and r["graded"]["pass"] else 0.0


def arm_order(arms):
    known = [a for a in common.ALL_ARMS if a in arms]
    return known + sorted(set(arms) - set(known))


def mean(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None


def mean_all(xs):
    """The mean, or None when any value is missing (a cold-start cost needs the run's stream)."""
    xs = list(xs)
    return None if not xs or any(x is None for x in xs) else sum(xs) / len(xs)


def arm_summary(runs):
    costs = [r["usage"].get("cost_usd") for r in runs]
    costs = [c for c in costs if c is not None]
    return {
        "n": len(runs),
        "success_rate": mean([succeeded(r) for r in runs]),
        "cost_mean": mean(costs),
        "cost_median": statistics.median(costs) if costs else None,
        "cost_cold_mean": mean_all(r.get("cost_cold") for r in runs),
        "client_cost_mean": mean([r["usage"].get("client_total_cost_usd") for r in runs]),
        **{f"tokens_{c}": mean([(r["usage"].get("tokens") or {}).get(c) for r in runs]) for c in TOKEN_CLASSES},
        "turns_mean": mean([r["usage"].get("num_turns") for r in runs]),
        "wall_mean_s": mean([r["meta"].get("wall_seconds") for r in runs]),
        "tool_calls_mean": mean([r["usage"].get("tool_calls_total") for r in runs]),
        "tool_result_chars_mean": mean([r["usage"].get("tool_result_chars") for r in runs]),
    }


def per_task(runs, cold=False):
    """{arm: {task: (mean success, mean cost)}} over each task's reps: the measured cost, or
    with cold=True the cold-start cost (None for a task where a run has none)."""
    groups = defaultdict(list)
    for r in runs:
        groups[(r["meta"]["arm"], r["meta"]["task_id"])].append(r)
    table = defaultdict(dict)
    for (arm, task), rs in groups.items():
        cost = mean_all(r.get("cost_cold") for r in rs) if cold else mean([r["usage"].get("cost_usd") for r in rs])
        table[arm][task] = (mean([succeeded(r) for r in rs]), cost)
    return table


def quantile(sorted_xs, q):
    pos = (len(sorted_xs) - 1) * q
    lo, hi = math.floor(pos), math.ceil(pos)
    return sorted_xs[lo] + (sorted_xs[hi] - sorted_xs[lo]) * (pos - lo)


def paired_stats(pairs):
    """pairs: [(success arm, success base, cost ratio or None)] -> (delta pp, geo mean ratio)."""
    delta = 100 * sum(a - b for a, b, _ in pairs) / len(pairs)
    logs = [math.log(r) for _, _, r in pairs if r]
    return delta, (math.exp(sum(logs) / len(logs)) if logs else None)


def bootstrap(pairs, resamples, seed):
    rng = random.Random(seed)
    deltas, ratios = [], []
    n = len(pairs)
    for _ in range(resamples):
        delta, ratio = paired_stats([pairs[rng.randrange(n)] for _ in range(n)])
        deltas.append(delta)
        if ratio is not None:
            ratios.append(ratio)
    deltas.sort()
    ratios.sort()
    ci = lambda xs: (quantile(xs, 0.025), quantile(xs, 0.975)) if xs else (None, None)
    return ci(deltas), ci(ratios)


def compare(table, arm, resamples, seed, margin_pp):
    tasks = sorted(set(table.get(arm, {})) & set(table.get(BASELINE, {})))
    if not tasks:
        return None
    pairs = []
    for t in tasks:
        (s_arm, c_arm), (s_base, c_base) = table[arm][t], table[BASELINE][t]
        ratio = c_arm / c_base if c_arm and c_base else None
        pairs.append((s_arm, s_base, ratio))
    delta, ratio = paired_stats(pairs)
    (d_lo, d_hi), (r_lo, r_hi) = bootstrap(pairs, resamples, seed)
    if d_lo > -margin_pp:
        verdict = "non-inferior"
    elif d_hi < -margin_pp:
        verdict = "inferior"
    else:
        verdict = "inconclusive"
    return {"tasks_paired": len(tasks), "delta_success_pp": delta, "delta_ci_low": d_lo,
            "delta_ci_high": d_hi, "cost_ratio_geo": ratio, "ratio_ci_low": r_lo,
            "ratio_ci_high": r_hi, "verdict": verdict}


def fmt(x, digits=2):
    if x is None:
        return "-"
    if isinstance(x, float):
        return f"{x:,.{digits}f}"
    return str(x)


def build(raw_dir, resamples=10_000, seed=20261010, margin_pp=5.0):
    runs = load_runs(raw_dir)
    good = scored(runs)
    arms = arm_order({r["meta"]["arm"] for r in runs if r["meta"].get("arm")})
    by_arm = {a: [r for r in good if r["meta"]["arm"] == a] for a in arms}
    summaries = {a: arm_summary(rs) for a, rs in by_arm.items()}
    table = per_task(good)
    comparisons = {a: compare(table, a, resamples, seed, margin_pp) for a in arms if a != BASELINE}
    cold_table = per_task(good, cold=True)
    for a, c in comparisons.items():
        if c:
            cold = compare(cold_table, a, resamples, seed, margin_pp)
            c.update(cost_ratio_cold_geo=cold["cost_ratio_geo"], ratio_cold_ci_low=cold["ratio_ci_low"],
                     ratio_cold_ci_high=cold["ratio_ci_high"])
    return runs, good, arms, summaries, table, comparisons


def write_csv(path, arms, summaries, comparisons):
    fields = ["arm"] + list(next(iter(summaries.values())).keys()) + [
        "tasks_paired", "delta_success_pp", "delta_ci_low", "delta_ci_high",
        "cost_ratio_geo", "ratio_ci_low", "ratio_ci_high", "verdict",
        "cost_ratio_cold_geo", "ratio_cold_ci_low", "ratio_cold_ci_high"]
    with open(path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        for a in arms:
            w.writerow({"arm": a, **summaries[a], **(comparisons.get(a) or {})})


def status_lines(runs):
    lines = []
    for r in runs:
        m = r["meta"]
        why = m.get("invalid_reason") or ""
        if m.get("status") != "ok":
            lines.append(f"| {m.get('run_id')} | {m.get('status')} | {why} |")
        elif m.get("flags"):
            lines.append(f"| {m.get('run_id')} | ok, flagged | {', '.join(m['flags'])} |")
        elif not r["graded"]:
            lines.append(f"| {m.get('run_id')} | ok, not graded | |")
        elif r["graded"].get("pass") is None:
            lines.append(f"| {m.get('run_id')} | ok, grading failed | {r['graded'].get('error', '')} |")
    return lines


def write_markdown(path, runs, good, arms, summaries, table, comparisons, args):
    out = ["# trust-me-bro report", "",
           f"{len(good)} scored runs (graded, or timed out or errored, which count as failures) out of {len(runs)}. "
           f"Bootstrap: {args.resamples} resamples over tasks, seed {args.seed}. "
           f"Non-inferiority margin: {args.margin_pp} percentage points of success. "
           "Cost: tokens x harness/prices.json (client estimate alongside). "
           "Cold start: the same runs, each session priced as if it had started with a cold prompt cache "
           "(docs/cache-isolation.md).", "",
           "## Per arm", "",
           "| arm | runs | success | cost mean $ | cost median $ | cold-start cost mean $ | client cost $ | input | output | cache read | cache write 5m | cache write 1h | turns | wall s | tool calls |",
           "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for a in arms:
        s = summaries[a]
        rate = f"{100 * s['success_rate']:.1f}%" if s["success_rate"] is not None else "-"
        out.append(f"| {a} | {s['n']} | {rate} | {fmt(s['cost_mean'], 4)} | {fmt(s['cost_median'], 4)} | "
                   f"{fmt(s['cost_cold_mean'], 4)} | {fmt(s['client_cost_mean'], 4)} | " +
                   " | ".join(fmt(s[f"tokens_{c}"], 0) for c in TOKEN_CLASSES) +
                   f" | {fmt(s['turns_mean'], 1)} | {fmt(s['wall_mean_s'], 0)} | {fmt(s['tool_calls_mean'], 1)} |")
    out += ["", f"## Paired with {BASELINE} (per-task means over reps)", "",
            "| arm | tasks | Δ success (pp) | 95% CI | cost ratio (geo mean) | 95% CI | cold-start cost ratio | 95% CI | success verdict |",
            "|---|---|---|---|---|---|---|---|---|"]
    for a, c in comparisons.items():
        if c is None:
            out.append(f"| {a} | 0 | - | - | - | - | - | - | no paired tasks |")
            continue
        out.append(f"| {a} | {c['tasks_paired']} | {fmt(c['delta_success_pp'], 1)} | "
                   f"[{fmt(c['delta_ci_low'], 1)}, {fmt(c['delta_ci_high'], 1)}] | {fmt(c['cost_ratio_geo'], 3)} | "
                   f"[{fmt(c['ratio_ci_low'], 3)}, {fmt(c['ratio_ci_high'], 3)}] | {fmt(c['cost_ratio_cold_geo'], 3)} | "
                   f"[{fmt(c['ratio_cold_ci_low'], 3)}, {fmt(c['ratio_cold_ci_high'], 3)}] | {c['verdict']} |")
    tasks = sorted({t for a in table for t in table[a]})
    out += ["", "## Per task (success rate / mean cost $)", "",
            "| task | " + " | ".join(arms) + " |", "|---" * (len(arms) + 1) + "|"]
    for t in tasks:
        cells = []
        for a in arms:
            s, c = table.get(a, {}).get(t, (None, None))
            cells.append("-" if s is None else f"{100 * s:.0f}% / {fmt(c, 3)}")
        out.append(f"| {t} | " + " | ".join(cells) + " |")
    counts = defaultdict(lambda: defaultdict(int))
    for r in runs:
        counts[r["meta"].get("arm")][r["meta"].get("status")] += 1
    out += ["", "## Run status per arm", "", "| arm | ok | timeout | error | invalid |", "|---|---|---|---|---|"]
    for a in arms:
        out.append(f"| {a} | " + " | ".join(str(counts[a][s]) for s in ("ok", "timeout", "error", "invalid")) + " |")
    lines = status_lines(runs)
    out += ["", "## Not scored or flagged", ""]
    out += (["| run | status | reason |", "|---|---|---|"] + lines) if lines else ["None."]
    Path(path).write_text("\n".join(out) + "\n")


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--raw", default=str(common.BENCH_ROOT / "results" / "raw"))
    p.add_argument("--out", default=str(common.BENCH_ROOT / "results"))
    p.add_argument("--margin-pp", type=float, default=5.0)
    p.add_argument("--resamples", type=int, default=10_000)
    p.add_argument("--seed", type=int, default=20261010)
    args = p.parse_args(argv)
    runs, good, arms, summaries, table, comparisons = build(args.raw, args.resamples, args.seed, args.margin_pp)
    if not runs:
        raise SystemExit(f"no runs under {args.raw}")
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    write_csv(out / "report.csv", arms, summaries, comparisons)
    write_markdown(out / "report.md", runs, good, arms, summaries, table, comparisons, args)
    print(f"wrote {out / 'report.md'} and {out / 'report.csv'}")


if __name__ == "__main__":
    main()
