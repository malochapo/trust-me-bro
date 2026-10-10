#!/usr/bin/env python3
"""Phase 0 leakage check: can the model answer a fact task without the code?

Each fact-graded task's prompt goes to the model with no repository and no tools, in
an empty directory, `--reps` times. A task answered correctly in any of them can be
answered from memory or guessed, so it does not measure the tools: drop or rewrite it.
Uses the judge's credentials (BENCH_KEY_JUDGE, else the subscription token).

Usage: python3 -I harness/leakage.py [--tasks 'tasks/*/task.json'] [--reps 3] [--out results/leakage]
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # -I leaves the script dir off sys.path

import argparse
import glob
import json
import subprocess
import tempfile

import common
import grade

PREAMBLE = (
    "You cannot see the repository the question is about and you have no tools. "
    "Answer from what you know, and still finish with the requested lines.\n\n"
)


def ask(prompt, model, claude, creds):
    with tempfile.TemporaryDirectory(prefix="leakage-") as tmp:
        home, cwd = Path(tmp) / "home", Path(tmp) / "work"
        (home / ".claude").mkdir(parents=True)
        cwd.mkdir()
        mcp = home / "mcp.json"
        mcp.write_text('{"mcpServers": {}}')
        env = common.clean_env(home, common.SYSTEM_PATH, creds)
        cmd = [claude, "-p", "--model", model, "--tools", "", "--output-format", "json",
               "--setting-sources", "user", "--strict-mcp-config", "--mcp-config", str(mcp)]
        r = subprocess.run(cmd, input=PREAMBLE + prompt, cwd=cwd, env=env,
                           capture_output=True, text=True, timeout=600)
    try:
        out = json.loads(r.stdout)
        return out.get("result") or "", out
    except ValueError:
        return "", {"error": (r.stdout + r.stderr)[-2000:]}


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--tasks", default="tasks/*/task.json")
    p.add_argument("--reps", type=int, default=3)
    p.add_argument("--model", default="claude-sonnet-5-5")
    p.add_argument("--plants", default="build/plants.json")
    p.add_argument("--out", default="results/leakage")
    p.add_argument("--claude-bin", default="claude")
    args = p.parse_args(argv)

    claude = common.resolve_bin(args.claude_bin)
    creds, auth = common.credentials("judge")
    if not auth and "stub" not in common.claude_version(claude):
        raise SystemExit("set BENCH_KEY_JUDGE (an API key) or BENCH_CLAUDE_OAUTH_TOKEN")
    plants = grade.load_plants(args.plants)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    leaked = []
    for task_file in sorted(glob.glob(args.tasks)):
        task = common.load_task(task_file)
        if (task.get("grader") or {}).get("kind") != "facts":
            continue
        passes = []
        for rep in range(1, args.reps + 1):
            answer, raw = ask(task["prompt"], args.model, claude, creds)
            verdict = grade.grade_facts(task["grader"], answer, plants)
            passes.append(verdict["pass"])
            common.write_json(out / f"{task['id']}__r{rep}.json",
                              {"answer": answer, "verdict": verdict, "raw": raw, "auth": auth})
        print(f"{'LEAKED' if any(passes) else 'ok    '} {task['id']}: {sum(passes)}/{args.reps} correct without the code")
        if any(passes):
            leaked.append(task["id"])
    common.write_json(out / "summary.json", {"leaked": leaked, "reps": args.reps, "model": args.model})
    return 1 if leaked else 0


if __name__ == "__main__":
    sys.exit(main())
