#!/usr/bin/env python3
"""Pilot 4's tables (docs/pilot-4.md): per part and model, each arm against native, and for
parts B and B2 what each arm saved on day 1 and what day 2 cost.

Per arm: runs, success, mean cost, turns, sobre tool calls and memory writes per run, and the
cost ratio to native (geometric mean of per-task ratios of means, 95% bootstrap interval over
tasks; with two tasks per part the interval says little), measured and with every session
started on a cold prompt cache (usage.cold_start, docs/cache-isolation.md). Day 2 is the last session
of a run that has more than one: its result's total_cost_usd, a running total within the session.

Usage: python3 -I harness/pilot4_summary.py [--pilot pilot5] [haiku sonnet]
(pilot 5 ran parts A and D again, with the released tools)
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

PARTS = {"A": ("long-",), "B": ("xs-reminders-next-day", "xs-dedup-next-day"),
         "B2": ("xs-reminders-saved", "xs-dedup-saved"), "C": ("ss-",),
         "D": ("mt-logs-case-cost", "mt-reminders-incident")}
SAVES = {"finding", "decision", "task", "remember", "gotcha"}
LOADS = {"load", "status", "resume", "recall", "search"}


def part_of(task):
    return next((p for p, prefixes in PARTS.items() if task.startswith(prefixes)), None)


def writes_memory(name, args):
    """A write to Claude Code's memory directory: with Write or Edit, or a shell redirection."""
    if name in ("Write", "Edit"):
        return "/memory/" in args.get("file_path", "")
    command = args.get("command", "") if name == "Bash" else ""
    return "/memory/" in command and any(w in command for w in (">", "tee "))


def read_run(run_dir):
    """What one run did, by session: sobre calls, memory saves and loads, and day 2's cost."""
    sessions, sobre, memory_writes = [], 0, 0
    saved, loaded = collections.Counter(), collections.Counter()
    cost_by_session = {}
    for line in open(run_dir / "stream.jsonl"):
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if event.get("type") == "system" and event.get("subtype") == "init":
            if not sessions or sessions[-1] != event.get("session_id"):
                sessions.append(event.get("session_id"))
        elif event.get("type") == "result":
            cost_by_session[event.get("session_id")] = event.get("total_cost_usd") or 0
        elif event.get("type") == "assistant":
            day = len(sessions)
            for block in event["message"].get("content", []):
                if block.get("type") != "tool_use":
                    continue
                name, args = block["name"], block.get("input", {})
                if name.startswith("mcp__sobre"):
                    sobre += 1
                    tool, action = name.split("__")[-1], args.get("action")
                    if tool in ("sobre_session", "sobre_knowledge") and action in SAVES:
                        saved[(day, "sobre")] += 1
                    if tool in ("sobre_session", "sobre_knowledge") and action in LOADS:
                        loaded[(day, "sobre")] += 1
                elif writes_memory(name, args):
                    memory_writes += 1
                    saved[(day, "Claude Code's memory")] += 1
    day2 = cost_by_session.get(sessions[-1]) if len(sessions) > 1 else None
    return dict(sobre=sobre, mem=memory_writes, day2=day2,
                saved_day1=sorted({where for (day, where) in saved if day == 1}),
                loaded_day2=any(day == 2 for (day, _) in loaded))


def load(model, pilot="pilot4"):
    runs = collections.defaultdict(list)
    for run_dir in sorted((common.BENCH_ROOT / "results" / pilot / model / "raw").iterdir()):
        meta, usage, graded = (common.read_json(run_dir / f) for f in ("meta.json", "usage.json", "graded.json"))
        if not (meta and usage and graded) or meta.get("status") != "ok":
            continue
        task, arm, _ = run_dir.name.split("__")
        runs[(task, arm)].append(dict(cost=usage["cost_usd"], cold=cold_cost(run_dir, usage), ok=bool(graded.get("pass")),
                                      turns=usage.get("num_turns") or 0, **read_run(run_dir)))
    return runs


def ratio_interval(ratios, rng):
    logs = [math.log(r) for r in ratios]
    boots = sorted(math.exp(statistics.mean(rng.choice(logs) for _ in logs)) for _ in range(10000))
    return math.exp(statistics.mean(logs)), boots[250], boots[9749]


def main(argv):
    pilot = "pilot4"
    if argv[:1] == ["--pilot"]:
        pilot, argv = argv[1], argv[2:]
    rng = random.Random(20261012)
    rng_cold = random.Random(20261012)  # its own stream, so the measured intervals stay as published
    for model in argv or ["haiku", "sonnet"]:
        runs = load(model, pilot)
        print(f"\n## {model}")
        for part in PARTS:
            tasks = sorted({t for t, _ in runs if part_of(t) == part})
            if not tasks:
                continue
            arms = sorted({a for t, a in runs if part_of(t) == part}, key=lambda a: (a != "native", a))
            print(f"\n### part {part} ({len(tasks)} tasks)\n")
            print("| arm | runs | success | mean cost | turns | sobre calls/run | memory writes/run | cost vs native (95% CI) "
                  "| cold start vs native (95% CI) | day-2 cost |")
            print("|---|---|---|---|---|---|---|---|---|---|")
            for arm in arms:
                rs = [r for t in tasks for r in runs.get((t, arm), [])]
                paired = [t for t in tasks if runs.get((t, arm)) and runs.get((t, "native"))]
                ratios = [statistics.mean(r["cost"] for r in runs[(t, arm)]) / statistics.mean(r["cost"] for r in runs[(t, "native")])
                          for t in paired]
                ratio = "1" if arm == "native" else "{:.2f} ({:.2f}–{:.2f})".format(*ratio_interval(ratios, rng))
                cold = "1" if arm == "native" else ""
                if arm != "native" and all(r["cold"] is not None for t in paired for r in runs[(t, arm)] + runs[(t, "native")]):
                    colds = [statistics.mean(r["cold"] for r in runs[(t, arm)]) / statistics.mean(r["cold"] for r in runs[(t, "native")])
                             for t in paired]
                    cold = "{:.2f} ({:.2f}–{:.2f})".format(*ratio_interval(colds, rng_cold))
                day2 = [r["day2"] for r in rs if r["day2"] is not None]
                print(f"| {arm} | {len(rs)} | {sum(r['ok'] for r in rs)}/{len(rs)} | ${statistics.mean(r['cost'] for r in rs):.4f} | "
                      f"{statistics.mean(r['turns'] for r in rs):.1f} | {statistics.mean(r['sobre'] for r in rs):.1f} | "
                      f"{statistics.mean(r['mem'] for r in rs):.1f} | {ratio} | {cold} | {f'${statistics.mean(day2):.4f}' if day2 else ''} |")
            if part in ("B", "B2"):
                print("\n| arm | saved on day 1 | day 2 loaded sobre's memory |")
                print("|---|---|---|")
                for arm in arms:
                    rs = [r for t in tasks for r in runs.get((t, arm), [])]
                    where = collections.Counter(" and ".join(r["saved_day1"]) or "nothing" for r in rs)
                    print(f"| {arm} | {', '.join(f'{k} {v}/{len(rs)}' for k, v in where.most_common())} | "
                          f"{sum(r['loaded_day2'] for r in rs)}/{len(rs)} |")


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
