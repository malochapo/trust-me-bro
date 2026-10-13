#!/usr/bin/env python3
"""The compaction position test (docs/compaction-position.md): pilot 4's two long sessions with the
/compact moved (tasks5/), run by Claude Code alone.

Per task and position: runs, success, facts recalled in the final recap from each half of the
session, hidden tests, cost (measured and with every session started cold), API requests,
compactions, the largest prompt, and the requests past Haiku 5.5's 100,000-token price tier.
Then each position's cost against the reference (-c3, the /compact between the two
investigations): ratio of mean costs per task, 95% bootstrap interval over runs within each
task, and the geometric mean over tasks.

Usage: python3 -I harness/compaction_position.py [--raw results/compaction-position/haiku/raw]
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # -I leaves the script dir off sys.path

import collections
import json
import math
import random
import statistics

import common
from usage import cold_cost

# The facts each recap must give, by the half of the session that found them.
FIRST_HALF = {
    "long-incident-then-dedup": {"file", "function", "commit", "image", "first-missed", "missing-field"},
    "long-security-then-redaction": {"create_case", "create_case_channel", "create_case_resources", "create_incident",
                                     "incident_delete_custom_event", "restored", "removed-by", "visibility-bug"},
}
POSITIONS = {0: "no /compact", 2: "after message 2", 3: "after message 3 (between the two)", 5: "after message 5"}
TIER = 100_000


def split_id(task_id):
    base, _, position = task_id.rpartition("-c")
    return base, int(position)


def facts(graded, base):
    """Facts matched in the recap, (first half, second half, totals), and must_not lines hit."""
    for part in graded.get("details", {}).get("parts", [graded]):
        if part.get("kind") == "facts":
            must = part["details"]["must"]
            first = [m for m in must if m["id"] in FIRST_HALF[base]]
            second = [m for m in must if m["id"] not in FIRST_HALF[base]]
            wrong = sum(bool(m.get("matched")) for m in part["details"].get("must_not", []))
            return (sum(m["matched"] for m in first), len(first), sum(m["matched"] for m in second), len(second), wrong)
    return None


def tests_pass(graded):
    return next((p.get("pass") for p in graded.get("details", {}).get("parts", []) if p.get("kind") == "tests"), None)


def scan(run_dir):
    """API requests of the main thread, compactions and their sizes, largest prompt, requests past the tier."""
    seen, requests, prompts, compactions = set(), 0, [], []
    for line in open(run_dir / "stream.jsonl"):
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if event.get("type") == "system" and event.get("subtype") == "compact_boundary":
            meta = event.get("compact_metadata") or {}
            compactions.append((meta.get("trigger"), meta.get("pre_tokens"), meta.get("post_tokens")))
        if event.get("type") != "assistant" or event.get("parent_tool_use_id"):
            continue
        message = event["message"]
        if message.get("id") in seen:
            continue
        seen.add(message.get("id"))
        requests += 1
        u = message.get("usage", {})
        prompts.append(u.get("input_tokens", 0) + u.get("cache_read_input_tokens", 0) + u.get("cache_creation_input_tokens", 0))
    return dict(requests=requests, max_prompt=max(prompts, default=0), over_tier=sum(p > TIER for p in prompts),
                compactions=compactions)


def load(raw):
    runs = collections.defaultdict(list)
    for run_dir in sorted(Path(raw).iterdir()):
        meta, usage, graded = (common.read_json(run_dir / f) for f in ("meta.json", "usage.json", "graded.json"))
        if not (meta and usage and graded) or meta.get("status") != "ok":
            continue
        base, position = split_id(meta["task_id"])
        runs[(base, position)].append(dict(ok=bool(graded.get("pass")), facts=facts(graded, base), tests=tests_pass(graded),
                                           cost=usage["cost_usd"], cold=cold_cost(run_dir, usage),
                                           turns=usage.get("num_turns") or 0, **scan(run_dir)))
    return runs


def ratio_interval(arm, ref, rng, n=4000):
    point = statistics.mean(arm) / statistics.mean(ref)
    boots = sorted(statistics.mean(rng.choices(arm, k=len(arm))) / statistics.mean(rng.choices(ref, k=len(ref)))
                   for _ in range(n))
    return point, boots[int(0.025 * n)], boots[int(0.975 * n) - 1]


def main(argv):
    raw = argv[argv.index("--raw") + 1] if "--raw" in argv else str(common.BENCH_ROOT / "results/compaction-position/haiku/raw")
    runs = load(raw)
    bases = sorted({b for b, _ in runs})
    rng = random.Random(20261013)
    for base in bases:
        print(f"\n### {base}\n")
        print("| /compact | runs | success | first-half facts | second-half facts | wrong lines | hidden tests | mean cost | "
              "cold start | requests | compactions (tokens before → after) | largest prompt | requests past 100K |")
        print("|---|---|---|---|---|---|---|---|---|---|---|---|---|")
        for position in sorted(p for b, p in runs if b == base):
            rs = runs[(base, position)]
            f = [r["facts"] for r in rs if r["facts"]]
            sizes = "; ".join(f"{pre:,} → {post:,}" for r in rs for _, pre, post in r["compactions"] if pre and post) or "none"
            print(f"| {POSITIONS.get(position, position)} | {len(rs)} | {sum(r['ok'] for r in rs)}/{len(rs)} | "
                  f"{sum(x[0] for x in f)}/{sum(x[1] for x in f)} | {sum(x[2] for x in f)}/{sum(x[3] for x in f)} | "
                  f"{sum(x[4] for x in f)} | {sum(bool(r['tests']) for r in rs)}/{len(rs)} | "
                  f"${statistics.mean(r['cost'] for r in rs):.4f} | ${statistics.mean(r['cold'] for r in rs):.4f} | "
                  f"{statistics.mean(r['requests'] for r in rs):.1f} | {sizes} | "
                  f"{max(r['max_prompt'] for r in rs):,} | {statistics.mean(r['over_tier'] for r in rs):.1f} |")
    print("\n### Cost against the /compact between the two investigations (-c3)\n")
    print("| /compact | " + " | ".join(bases) + " | geometric mean over tasks |")
    print("|---|" + "---|" * (len(bases) + 1))
    for position in sorted({p for _, p in runs} - {3}):
        cells, logs = [], []
        for base in bases:
            arm, ref = runs.get((base, position)), runs.get((base, 3))
            if not (arm and ref):
                cells.append("")
                continue
            point, low, high = ratio_interval([r["cold"] for r in arm], [r["cold"] for r in ref], rng)
            cells.append(f"{point:.2f} ({low:.2f}–{high:.2f})")
            logs.append(math.log(point))
        geo = f"{math.exp(statistics.mean(logs)):.2f}" if len(logs) == len(bases) else ""
        print(f"| {POSITIONS.get(position, position)} | " + " | ".join(cells) + f" | {geo} |")
    print("\nCosts are cold-start costs (docs/cache-isolation.md); 95% bootstrap intervals over runs, seed 20261013.")


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
