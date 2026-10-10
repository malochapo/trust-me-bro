#!/usr/bin/env python3
"""Runs a matrix of (task, arm, rep), then grades it.

For each rep and each task (tasks shuffled per rep), every arm runs back to back in a
random order drawn from a fixed seed, so drift over the hours of a bench (API latency,
rate limits, cache state) does not favor one arm. Runs whose meta.json says ok,
timeout or error are skipped; invalid runs are run again (--rerun-errors also re-runs
timeouts and errors). Each ok run is graded as soon as it ends, then its work dir
(checkout, venv, home) is deleted unless --keep-work: a run takes a few hundred MB.
Any ok run still without graded.json is graded at the end.

Runs are sequential by default. --jobs N runs N at a time, each on its own Postgres
server: ports --first-port (5432) to --first-port+N-1 (BENCH_DB_PORT for run.py and grade.py, see common.py).
Every server needs the same user and password (postgres / dispatch).

Usage: python3 -I harness/bench.py --tasks 'tasks/*/task.json' --arms native,sobre --reps 3
Extra run.py options go after "--", e.g. `-- --effort high --timeout-min 30`.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # -I leaves the script dir off sys.path

import argparse
import glob
import os
import queue
import random
import shutil
import subprocess
import threading

import common
from run import run_id_for

HERE = Path(__file__).resolve().parent


def schedule(task_files, arms, reps, seed):
    rng = random.Random(seed)
    plan = []
    for rep in range(1, reps + 1):
        tasks = list(task_files)
        rng.shuffle(tasks)
        for task_file in tasks:
            plan.extend((task_file, arm, rep) for arm in rng.sample(arms, len(arms)))
    return plan


def needs_run(run_dir, rerun_errors):
    meta = common.read_json(run_dir / "meta.json")
    if meta is None:
        return True
    status = meta.get("status")
    return status == "invalid" or (rerun_errors and status in ("timeout", "error"))


def spent_usd(out):
    """Computed cost of every run under out, judge calls excluded."""
    return sum((common.read_json(u, {}) or {}).get("cost_usd") or 0 for u in Path(out).glob("*/usage.json"))


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    passthrough = argv[argv.index("--") + 1:] if "--" in argv else []
    argv = argv[:argv.index("--")] if "--" in argv else argv
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--tasks", default="tasks/*/task.json",
                   help="glob(s), comma separated, relative to the bench root")
    p.add_argument("--arms", default=",".join(common.ALL_ARMS))
    p.add_argument("--reps", type=int, default=1)
    p.add_argument("--seed", type=int, default=20261010)
    p.add_argument("--out", default=str(common.BENCH_ROOT / "results" / "raw"))
    p.add_argument("--claude-bin", default="claude", help="for the runs and the judge")
    p.add_argument("--judge-model", default="claude-sonnet-5-5")
    p.add_argument("--rerun-errors", action="store_true")
    p.add_argument("--no-grade", action="store_true")
    p.add_argument("--keep-work", action="store_true", help="keep each run's work dir")
    p.add_argument("--stop-at-usd", type=float, default=None,
                   help="stop before a run once the computed cost of every run in --out reaches this")
    p.add_argument("--dry-run", action="store_true", help="print the plan and exit")
    p.add_argument("--jobs", type=int, default=1, help="runs at a time, one Postgres server each")
    p.add_argument("--first-port", type=int, default=5432, help="the first of the --jobs Postgres ports")
    args = p.parse_args(argv)

    task_files = sorted({f for pattern in args.tasks.split(",") if pattern
                         for f in glob.glob(pattern if Path(pattern).is_absolute()
                                            else str(common.BENCH_ROOT / pattern))})
    arms = [a for a in args.arms.split(",") if a]
    if not task_files:
        raise SystemExit(f"no task matches {args.tasks}")
    plan = schedule(task_files, arms, args.reps, args.seed)
    out = Path(args.out).resolve()

    todo = []
    for task_file, arm, rep in plan:
        run_id = run_id_for(common.load_task(task_file)["id"], arm, rep)
        if needs_run(out / run_id, args.rerun_errors):
            todo.append((task_file, arm, rep, run_id))
    print(f"{len(plan)} runs planned, {len(todo)} to do")
    if args.dry_run:
        for _, _, _, run_id in todo:
            print(run_id)
        return 0
    ports = [args.first_port + i for i in range(max(1, args.jobs))]
    if todo and "--no-pg-check" not in passthrough:
        down = [port for port in ports if not common.postgres_ready(port=port)]
        if down:
            raise SystemExit(f"Postgres is not reachable on localhost port(s) {down} (pg_isready -h localhost -p PORT)")
        problems = [p for p in (common.postgres_encoding_problem(port=port) for port in ports) if p]
        if problems:
            raise SystemExit("; ".join(problems))

    grade_opts = ["--claude-bin", args.claude_bin, "--judge-model", args.judge_model]
    items = queue.Queue()
    for i, item in enumerate(todo, 1):
        items.put((i, item))
    print_lock, stopped = threading.Lock(), threading.Event()

    def say(text):
        with print_lock:
            print(text, flush=True)

    def worker(port):
        env = {**os.environ, "BENCH_DB_PORT": str(port)}
        while not stopped.is_set():
            try:
                i, (task_file, arm, rep, run_id) = items.get_nowait()
            except queue.Empty:
                return
            spent = spent_usd(out)
            if args.stop_at_usd is not None and spent >= args.stop_at_usd:
                say(f"stopping: ${spent:.2f} spent, limit ${args.stop_at_usd:.2f}")
                stopped.set()
                return
            say(f"[{i}/{len(todo)}] {run_id} (${spent:.2f} spent so far)"
                + (f" [db {port}]" if len(ports) > 1 else ""))
            force = ["--force"] if (out / run_id).exists() else []
            subprocess.run([sys.executable, "-I", str(HERE / "run.py"), "--task-file", task_file,
                            "--arm", arm, "--rep", str(rep), "--out", str(out), "--claude-bin", args.claude_bin,
                            *force, *passthrough], env=env)
            meta = common.read_json(out / run_id / "meta.json") or {}
            if meta.get("status") == "ok" and not args.no_grade:
                subprocess.run([sys.executable, "-I", str(HERE / "grade.py"), str(out / run_id), *grade_opts], env=env)
            work = (meta.get("work") or {}).get("dir")
            if work and not args.keep_work:
                shutil.rmtree(work, ignore_errors=True)

    threads = [threading.Thread(target=worker, args=(port,)) for port in ports]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    if args.no_grade:
        return 0
    for task_file, arm, rep in plan:
        run_dir = out / run_id_for(common.load_task(task_file)["id"], arm, rep)
        meta = common.read_json(run_dir / "meta.json") or {}
        if meta.get("status") == "ok" and not (run_dir / "graded.json").exists():
            subprocess.run([sys.executable, "-I", str(HERE / "grade.py"), str(run_dir), *grade_opts])
    return 0


if __name__ == "__main__":
    sys.exit(main())
