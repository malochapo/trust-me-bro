"""Checks every task against its reference answer.

Test-graded tasks: the hidden tests must fail on the fixture as built, and pass,
together with the regression command, once solution.patch is applied.
Fact-graded tasks: golden.md must pass the grader and wrong.md (the answer
upstream code or memory gives) must fail it.
Tasks graded on both (grader kind "all", e.g. a multi-turn task that changes the code
and ends with a recap): each part is checked as above. Grading only sees the final
state and the last answer, so a task's `followups` play no part here.

Usage: python3 -I tasks/validate.py --fixture build/fixture.git --deps-venv DIR [--tasks-dir DIR] [task ...]
Needs PostgreSQL on localhost (user postgres, password dispatch) and uv. BENCH_DB_PORT
picks the server, as for the harness (default 5432; Dispatch reads it as DATABASE_PORT).
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

TASKS = Path(__file__).resolve().parent
DB_PORT = int(os.environ.get("BENCH_DB_PORT") or 5432)
# what harness/grade.py runs when a tests grader has no `regression`
DEFAULT_REGRESSION = ["python", "-m", "pytest", "-q", "-p", "no:cacheprovider", "tests/signal"]


def run(cmd, cwd=None, env=None, check=True):
    result = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True)
    if check and result.returncode != 0:
        sys.exit(f"{' '.join(map(str, cmd))} failed:\n{result.stdout[-3000:]}\n{result.stderr[-3000:]}")
    return result


def make_env(work, fixture, deps_venv):
    repo, venv = work / "repo", work / "venv"
    run(["git", "clone", "--quiet", str(fixture), str(repo)])
    run(["uv", "venv", "-q", "-p", "3.11", str(venv)])
    purelib = lambda py: run([str(py), "-c", "import sysconfig; print(sysconfig.get_paths()['purelib'])"]).stdout.strip()
    Path(purelib(venv / "bin/python"), "_bench_deps.pth").write_text(purelib(deps_venv / "bin/python") + "\n")
    run(["uv", "pip", "install", "-q", "--no-deps", "--no-build-isolation", "-e", str(repo)],
        env={"VIRTUAL_ENV": str(venv), "PATH": "/usr/local/bin:/usr/bin:/bin:" + str(Path.home() / ".local/bin")})
    return repo, venv


def reset(repo):
    run(["git", "checkout", "--quiet", "."], cwd=repo)
    run(["git", "clean", "-qfdx", "-e", "*.egg-info"], cwd=repo)


FIXTURE_HEAD = "HEAD"


def parts(grader):
    """The graders a task is graded by: its own, or each part of an "all" grader."""
    return grader["graders"] if grader["kind"] == "all" else [grader]


def tests_pass(repo, venv, command):
    command = [c.replace("{FIXTURE_HEAD}", FIXTURE_HEAD) for c in command]
    env = {"PATH": f"{venv / 'bin'}:/usr/bin:/bin", "HOME": str(Path.home()), "LANG": "C.UTF-8"}
    if DB_PORT != 5432:
        env["DATABASE_PORT"] = str(DB_PORT)
    result = run(command, cwd=repo, env=env, check=False)
    return result.returncode == 0, result.stdout.strip().splitlines()[-1:] if result.stdout else result.stderr[-300:]


def validate_tests(task_dir, grader, repo, venv):
    hidden = task_dir / "hidden"

    reset(repo)
    if hidden.is_dir():
        shutil.copytree(hidden, repo, dirs_exist_ok=True)
    ok, tail = tests_pass(repo, venv, grader["command"])
    problems = [] if not ok else [f"hidden tests pass on the unfixed fixture: {tail}"]

    reset(repo)
    run(["git", "apply", str(task_dir / "solution.patch")], cwd=repo)
    if hidden.is_dir():
        shutil.copytree(hidden, repo, dirs_exist_ok=True)
    ok, tail = tests_pass(repo, venv, grader["command"])
    if not ok:
        problems.append(f"hidden tests fail with the solution: {tail}")
    regression = grader.get("regression", DEFAULT_REGRESSION)
    if regression:
        ok, tail = tests_pass(repo, venv, regression)
        if not ok:
            problems.append(f"regression fails with the solution: {tail}")
    reset(repo)
    return problems


def facts_pass(grader, answer, plants):
    import re

    def resolve(pattern):
        def sub(m):
            sha = plants[m.group(1)]
            return sha[:8] if m.group(2) else sha
        return re.sub(r"\{plant:([\w-]+)(:short)?\}", sub, pattern)

    answer = resolve(answer)
    musts = all(any(re.search(resolve(p), answer, re.I | re.M) for p in m["any_of"]) for m in grader["must"])
    nots = any(re.search(resolve(m["regex"]), answer, re.I | re.M) for m in grader.get("must_not", []))
    return musts and not nots


def validate_facts(task_dir, grader, plants):
    problems = []
    if not facts_pass(grader, (task_dir / "golden.md").read_text(), plants):
        problems.append("golden.md fails the grader")
    if facts_pass(grader, (task_dir / "wrong.md").read_text(), plants):
        problems.append("wrong.md passes the grader")
    return problems


def report(task_dir, problems):
    print(f"{'FAIL' if problems else 'ok  '} {task_dir.name}")
    for p in problems:
        print(f"     {p}")
    return bool(problems)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--fixture", type=Path, required=True)
    parser.add_argument("--deps-venv", type=Path, required=True)
    parser.add_argument("--tasks-dir", type=Path, default=TASKS, help="e.g. tasks2 for pilot 2")
    parser.add_argument("tasks", nargs="*")
    args = parser.parse_args()

    root = args.tasks_dir.resolve()
    dirs = [root / t for t in args.tasks] or sorted(d for d in root.iterdir() if (d / "task.json").exists())
    graders = {d: json.loads((d / "task.json").read_text())["grader"] for d in dirs}
    kinds = lambda d: [g["kind"] for g in parts(graders[d])]
    built = json.loads((args.fixture.resolve().parent / "plants.json").read_text())
    plants = {**built.get("replayed", {}), **built["plants"]}
    global FIXTURE_HEAD
    FIXTURE_HEAD = built["head"]

    # fact-graded parts need no database: check them first, and report the tasks that have nothing else
    facts = {d: [p for g in parts(graders[d]) if g["kind"] == "facts" for p in validate_facts(d, g, plants)]
             for d in dirs if "facts" in kinds(d)}
    failed = False
    for d in [d for d in dirs if d in facts and "tests" not in kinds(d)]:
        failed |= report(d, facts[d])

    dirs = [d for d in dirs if "tests" in kinds(d)]
    if not dirs:
        sys.exit(1 if failed else 0)
    with tempfile.TemporaryDirectory() as tmp:
        repo, venv = make_env(Path(tmp), args.fixture.resolve(), args.deps_venv.resolve())
        for d in dirs:
            both = "facts" in kinds(d)
            problems = [f"facts: {p}" for p in facts.get(d, [])] if both else []
            for g in [g for g in parts(graders[d]) if g["kind"] == "tests"]:
                problems += [f"tests: {p}" if both else p for p in validate_tests(d, g, repo, venv)]
            failed |= report(d, problems)
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
