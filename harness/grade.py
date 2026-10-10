#!/usr/bin/env python3
"""Grades one run against its task and writes graded.json in the run dir.

Grader kinds (task.json `grader.kind`):
  facts  `must` = [{id, any_of: [regex]}], `must_not` = [{id, regex}], matched against
         answer.md, case-insensitive and multi-line. Regexes may name planted commits:
         {plant:<id>} (full sha) and {plant:<id>:short} (8 chars), from build/plants.json.
         score = matched / len(must); pass = every must matched and no must_not did.
  tests  copies tasks/<id>/hidden/ over the run's repo, runs `command` there with the
         run's virtualenv first on PATH, then `regression` (default: the signal test
         suite; [] for none). pass = both exit 0. Logs: grade_tests.log, grade_regression.log.
         Serial: the fixture's tests use one fixed Postgres database.
  judge  harness/judge.py; pass = score >= grader.pass_score (default 2).

Usage: python3 -I harness/grade.py <run dir> [<run dir> ...] [--force]
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # -I leaves the script dir off sys.path

import argparse
import os
import re
import shutil
import subprocess
import tempfile
import time

import common
import judge

DEFAULT_REGRESSION = ["python", "-m", "pytest", "-q", "-p", "no:cacheprovider", "tests/signal"]
TEST_TIMEOUT_S = 15 * 60
PLACEHOLDER = re.compile(r"\{plant:([A-Za-z0-9_.-]+?)(:short)?\}")


def load_plants(path):
    """Plant ids and replayed upstream commits (by their upstream sha) -> fixture commit ids."""
    data = common.read_json(path, {}) or {}
    if "plants" not in data:
        return data
    return {**data.get("replayed", {}), **data["plants"]}


def resolve_plants(pattern, plants):
    def sub(m):
        if m.group(1) not in plants:
            raise KeyError(f"unknown plant {m.group(1)!r} in {pattern!r}")
        sha = plants[m.group(1)]
        return re.escape(sha[:8] if m.group(2) else sha)
    return PLACEHOLDER.sub(sub, pattern)


def search(pattern, text, plants):
    return re.search(resolve_plants(pattern, plants), text, re.IGNORECASE | re.MULTILINE)


def plants_for(meta):
    """The plants of the fixture the run used: its plants.json sits next to fixture.git."""
    beside = Path(meta.get("fixture") or "").parent / "plants.json"
    return beside if beside.is_file() else common.DEFAULT_PLANTS


def grade_facts(grader, answer, plants):
    must = []
    for item in grader.get("must") or []:
        hit = next((p for p in item["any_of"] if search(p, answer, plants)), None)
        must.append({"id": item["id"], "matched": hit is not None, "pattern": hit})
    must_not = [{"id": item["id"], "matched": bool(search(item["regex"], answer, plants))}
                for item in grader.get("must_not") or []]
    matched = sum(m["matched"] for m in must)
    return {
        "score": matched / len(must) if must else 1.0,
        "pass": matched == len(must) and not any(m["matched"] for m in must_not),
        "details": {"must": must, "must_not": must_not},
    }


def run_logged(cmd, cwd, env, log_path):
    start = time.monotonic()
    with open(log_path, "w") as log:
        log.write(f"$ {' '.join(cmd)}\n")
        log.flush()
        try:
            rc = subprocess.run(cmd, cwd=cwd, env=env, stdin=subprocess.DEVNULL, stdout=log,
                                stderr=subprocess.STDOUT, timeout=TEST_TIMEOUT_S).returncode
        except subprocess.TimeoutExpired:
            rc = "timeout"
    tail = Path(log_path).read_text(errors="replace").strip().splitlines()[-1:]
    return {"cmd": cmd, "exit": rc, "seconds": round(time.monotonic() - start, 1),
            "last_line": tail[0] if tail else ""}


def rebuild_work(meta, run_dir, base):
    """A fresh checkout with the run's changes and its own venv, when the run's work dir is gone.

    bench.py deletes each run's work dir once graded. To re-grade (after a grader fix), the
    fixture is cloned at the run's starting commit and changes.patch (untracked files
    included) is applied on top.
    """
    repo, venv = base / "repo", base / "venv"
    subprocess.run(["git", "clone", "--quiet", meta["fixture"], str(repo)], check=True)
    subprocess.run(["git", "checkout", "--quiet", meta["fixture_head"]], cwd=repo, check=True)
    patch = run_dir / "changes.patch"
    if patch.exists() and patch.stat().st_size:
        subprocess.run(["git", "apply", "--whitespace=nowarn", str(patch)], cwd=repo, check=True)
    deps = os.environ.get("BENCH_DEPS_VENV")
    if not deps:
        raise SystemExit("set BENCH_DEPS_VENV to rebuild a run's venv")
    with open(run_dir / "rebuild.log", "w") as log:
        common.build_run_venv(venv, repo, deps, log)
    return {"repo": str(repo), "venv": str(venv)}


def grade_tests(grader, task, run_dir, meta):
    repo, scratch = Path(meta["work"]["repo"]), None
    if not repo.is_dir():
        scratch = tempfile.mkdtemp(prefix="regrade-")
        meta = {**meta, "work": {**meta["work"], **rebuild_work(meta, run_dir, Path(scratch))}}
        repo = Path(meta["work"]["repo"])
    hidden = Path(task["_dir"]) / "hidden"
    copied = []
    if hidden.is_dir():
        for src in sorted(p for p in hidden.rglob("*") if p.is_file()):
            dest = repo / src.relative_to(hidden)
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)
            copied.append(str(src.relative_to(hidden)))
    venv = meta["work"].get("venv")
    path = ([Path(venv) / "bin"] if venv else []) + common.extra_path_dirs() + common.SYSTEM_PATH
    regression = grader.get("regression", DEFAULT_REGRESSION)
    if not common.postgres_ready():
        raise SystemExit("Postgres is not reachable on localhost:5432")
    # {FIXTURE_HEAD} lets a command restore files from the commit the run started from,
    # e.g. the original tests, so that a run cannot pass by editing them.
    fill = lambda cmd: [c.replace("{FIXTURE_HEAD}", meta.get("fixture_head") or "HEAD") for c in cmd] if cmd else cmd
    with tempfile.TemporaryDirectory(prefix="grade-home-") as home, common.bench_lock():
        env = common.clean_env(home, path)
        tests = run_logged(fill(grader["command"]), repo, env, run_dir / "grade_tests.log")
        reg = run_logged(fill(regression), repo, env, run_dir / "grade_regression.log") if regression else None
    ok = tests["exit"] == 0 and (reg is None or reg["exit"] == 0)
    if scratch:
        shutil.rmtree(scratch, ignore_errors=True)
    return {"score": 1.0 if ok else 0.0, "pass": ok,
            "details": {"hidden_files": copied, "tests": tests, "regression": reg}}


def grade_judge(grader, task, run_dir, args):
    verdict = judge.judge_run(run_dir, task, args.judge_model, args.claude_bin)
    if "score" not in verdict:
        return {"score": None, "pass": None, "details": verdict, "error": verdict.get("error")}
    return {"score": verdict["score"] / 3, "pass": verdict["score"] >= grader.get("pass_score", 2),
            "details": verdict}


def grade_run(run_dir, args):
    run_dir = Path(run_dir).resolve()
    meta = common.read_json(run_dir / "meta.json")
    if meta is None:
        raise SystemExit(f"{run_dir}: no meta.json")
    if meta.get("status") == "invalid":
        raise SystemExit(f"{run_dir}: invalid run ({meta.get('invalid_reason')}), re-run it instead")
    task = common.load_task(args.task_file or meta["task_file"])
    grader = task["grader"]
    kind = grader["kind"]
    answer = (run_dir / "answer.md").read_text() if (run_dir / "answer.md").exists() else ""
    if kind == "facts":
        graded = grade_facts(grader, answer, load_plants(args.plants or plants_for(meta)))
    elif kind == "tests":
        graded = grade_tests(grader, task, run_dir, meta)
    elif kind == "judge":
        graded = grade_judge(grader, task, run_dir, args)
    else:
        raise SystemExit(f"unknown grader kind {kind!r}")
    graded.update(run_id=meta["run_id"], task_id=task["id"], arm=meta["arm"], rep=meta["rep"],
                  kind=kind, task_sha256=common.sha256_file(task["_file"]), graded_at=common.utc_now())
    if graded["task_sha256"] != meta.get("task_sha256"):
        graded["warning"] = "task.json changed since the run"
    common.write_json(run_dir / "graded.json", graded)
    return graded


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("run_dirs", nargs="+")
    p.add_argument("--task-file", help="default: the task_file recorded in meta.json")
    p.add_argument("--plants", default=None,
                   help="default: plants.json next to the run's fixture, else " + str(common.DEFAULT_PLANTS))
    p.add_argument("--judge-model", default="claude-sonnet-5-5")
    p.add_argument("--claude-bin", default="claude")
    p.add_argument("--force", action="store_true", help="re-grade runs that have graded.json")
    args = p.parse_args(argv)
    failed = 0
    for run_dir in args.run_dirs:
        if (Path(run_dir) / "graded.json").exists() and not args.force:
            print(f"{run_dir}: already graded")
            continue
        try:
            g = grade_run(run_dir, args)
            print(f"{g['run_id']}: {g['kind']} pass={g['pass']} score={g['score']}")
        except SystemExit as e:
            print(e, file=sys.stderr)
            failed = 1
    return failed


if __name__ == "__main__":
    sys.exit(main())
