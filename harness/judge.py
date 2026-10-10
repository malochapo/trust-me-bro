#!/usr/bin/env python3
"""Blind LLM judge for free-text answers (grader kind "judge").

The judge gets the question, the reference answer, the rubric (scores 0-3) and the
candidate answer with every arm-revealing string replaced by "[tool]". It runs as
`claude -p` with no tools, an empty config dir, a neutral working directory and an
environment built from nothing, and must reply through a JSON schema
{score: 0-3, reasons}. The exact prompt and reply are saved in the run dir
(judge_prompt.txt, judge_reply.json). Nothing it sees names the arm or the run.

Usage: python3 -I harness/judge.py <run dir> [--judge-model M] [--claude-bin B]
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # -I leaves the script dir off sys.path

import argparse
import json
import re
import subprocess
import tempfile

import common

# Longest patterns first, so "mcp__sobre__sobre_read" goes as one piece.
REDACTIONS = [
    r"mcp__\S+",
    r"sobre_\w+",
    r"ctx_\w+",
    r"<<ccr:[^>]*>>",  # headroom's compress-cache-retrieve markers
    r"lean[-_]?ctx",
    r"sobre",
    r"headroom",
    r"rtk",
]
REDACT_RE = re.compile("|".join(REDACTIONS), re.IGNORECASE)

SCHEMA = {
    "type": "object",
    "properties": {
        "score": {"type": "integer", "minimum": 0, "maximum": 3},
        "reasons": {"type": "string"},
    },
    "required": ["score", "reasons"],
    "additionalProperties": False,
}

PROMPT = """You are grading an answer to a question about a software repository.
Compare the candidate answer with the reference answer and score it with the rubric.
Judge only what the answer says; ignore its style and length. The string "[tool]"
replaces names that do not matter for grading.

## Question

{question}

## Reference answer

{reference}

## Rubric (score 0 to 3)

{rubric}

## Candidate answer

<candidate>
{candidate}
</candidate>

Reply with the score (an integer from 0 to 3) and short reasons.
"""


def redact(text):
    return REDACT_RE.sub("[tool]", text)


def build_prompt(task, answer):
    grader = task.get("grader") or {}
    question = task["prompt"].replace("{DATA_DIR}", "<data directory>")
    return PROMPT.format(question=question.strip(), reference=str(grader.get("reference", "")).strip(),
                         rubric=str(grader.get("rubric", "")).strip(), candidate=redact(answer).strip())


def ask(prompt, model, claude, creds):
    """Runs the judge once; returns (reply text, parsed {score, reasons} or None)."""
    with tempfile.TemporaryDirectory(prefix="judge-") as tmp:
        home, cwd = Path(tmp) / "home", Path(tmp) / "work"
        (home / ".claude").mkdir(parents=True)
        cwd.mkdir()
        mcp = home / "mcp.json"
        mcp.write_text('{"mcpServers": {}}')
        env = common.clean_env(home, common.SYSTEM_PATH)
        env.update(creds)
        cmd = [claude, "-p", "--model", model, "--tools", "", "--output-format", "json",
               "--json-schema", json.dumps(SCHEMA), "--setting-sources", "user",
               "--strict-mcp-config", "--mcp-config", str(mcp)]
        r = subprocess.run(cmd, input=prompt, cwd=cwd, env=env, capture_output=True, text=True, timeout=600)
    reply = r.stdout
    try:
        out = json.loads(reply).get("structured_output") or {}
        score = out.get("score")
        if isinstance(score, int) and 0 <= score <= 3:
            return reply, {"score": score, "reasons": str(out.get("reasons", ""))}
    except (ValueError, AttributeError):
        pass
    return reply + r.stderr, None


def judge_run(run_dir, task, model="claude-sonnet-5-5", claude_bin="claude"):
    run_dir = Path(run_dir)
    claude = common.resolve_bin(claude_bin)
    creds, auth = common.credentials("judge")
    if not auth and "stub" not in common.claude_version(claude):
        raise SystemExit("set BENCH_KEY_JUDGE (an API key) or BENCH_CLAUDE_OAUTH_TOKEN for the judge")
    answer = (run_dir / "answer.md").read_text() if (run_dir / "answer.md").exists() else ""
    prompt = build_prompt(task, answer)
    (run_dir / "judge_prompt.txt").write_text(prompt)
    reply, verdict = ask(prompt, model, claude, creds)
    (run_dir / "judge_reply.json").write_text(reply)
    if verdict is None:
        return {"error": "the judge gave no valid {score, reasons}", "judge_model": model}
    return {**verdict, "judge_model": model}


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("run_dir")
    p.add_argument("--task-file", help="default: the task_file recorded in meta.json")
    p.add_argument("--judge-model", default="claude-sonnet-5-5")
    p.add_argument("--claude-bin", default="claude")
    args = p.parse_args(argv)
    meta = common.read_json(Path(args.run_dir) / "meta.json", {})
    task = common.load_task(args.task_file or meta["task_file"])
    print(json.dumps(judge_run(args.run_dir, task, args.judge_model, args.claude_bin), indent=2))


if __name__ == "__main__":
    main()
