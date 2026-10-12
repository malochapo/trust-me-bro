#!/usr/bin/env python3
"""What tool results cost in native runs, and the part a build's hook would remove.

A tool result is written to the cache once, then read again at every later API call of the
same session. Each call's new prompt tokens (cache writes plus uncached input, minus the
previous call's output) are the results and messages added since the previous call; a result
gets its share of them by characters. The hook replay sends each Bash result of a native run
through `<build> hook compress` and counts what it removes, on the same path: it says nothing
about a path the agent would have taken with the hook.

Usage: python3 -I harness/result_share.py results/pilot4 [--tasks 'mt-*'] [--hook name=path ...]
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # -I leaves the script dir off sys.path

import argparse
import collections
import glob
import json
import statistics
import subprocess
import tempfile

import common

PRICES = json.loads((common.BENCH_ROOT / "harness" / "prices.json").read_text())["models"]
MIN_HOOKED_CHARS = 400  # the hook leaves shorter outputs alone


def result_text(block):
    content = block.get("content")
    if isinstance(content, str):
        return content
    return "".join(x.get("text", "") for x in (content or []) if isinstance(x, dict))


def calls_of(stream):
    """API calls in order: (usage, session id, [(result chars, Bash command or None, text)] added before it)."""
    calls, by_id, pending, commands, session = [], {}, [], {}, None
    for line in open(stream):
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if event.get("type") == "system" and event.get("subtype") == "init":
            session = event.get("session_id")
        elif event.get("type") == "assistant":
            message = event["message"]
            if message.get("id") not in by_id:
                by_id[message.get("id")] = len(calls)
                calls.append([message.get("usage", {}), session, pending])
                pending = []
            elif message.get("usage"):
                calls[by_id[message["id"]]][0] = message["usage"]
            for block in message.get("content", []):
                if block.get("type") == "tool_use":
                    commands[block["id"]] = block.get("input", {}).get("command") if block["name"] == "Bash" else None
        elif event.get("type") == "user" and isinstance(event.get("message", {}).get("content"), list):
            for block in event["message"]["content"]:
                if isinstance(block, dict) and block.get("type") == "tool_result":
                    text = result_text(block)
                    pending.append((len(text), commands.get(block.get("tool_use_id")), text))
    return calls


def removed_by_hook(binary, command, text, home):
    if command is None or len(text) < MIN_HOOKED_CHARS:
        return 0
    payload = json.dumps({"hook_event_name": "PostToolUse", "tool_name": "Bash", "tool_input": {"command": command},
                          "tool_response": {"stdout": text, "stderr": "", "interrupted": False, "isImage": False}})
    r = subprocess.run([binary, "hook", "compress"], input=payload, capture_output=True, text=True,
                       env={"HOME": home, "PATH": "/usr/bin:/bin"}, timeout=60)
    out = text
    if r.stdout.strip():
        try:
            out = json.loads(r.stdout)["hookSpecificOutput"]["updatedToolOutput"]["stdout"]
        except (ValueError, KeyError, TypeError):
            pass
    return max(len(text) - len(out.split("\n[sobre: output compressed")[0]), 0)


def run_shares(run_dir, hooks, home):
    """(share of the run's cost that its tool results account for, {hook: share it would remove})."""
    usage = common.read_json(run_dir / "usage.json") or {}
    model = next(iter(usage.get("by_model", {})), None)
    if model not in PRICES or not usage.get("cost_usd"):
        return None
    write, read = PRICES[model]["cache_write_5m"] / 1e6, PRICES[model]["cache_read"] / 1e6
    calls = calls_of(run_dir / "stream.jsonl")
    results_cost, removed = 0.0, collections.Counter()
    previous_output = 0
    for i, (call_usage, session, results) in enumerate(calls):
        chars = sum(n for n, _, _ in results)
        if chars:
            new_tokens = max(call_usage.get("cache_creation_input_tokens", 0) + call_usage.get("input_tokens", 0)
                             - previous_output, 0)
            tokens = new_tokens * chars / (chars + 200)  # a little is the assistant text around them
            later_calls = sum(1 for c in calls[i + 1:] if c[1] == session)
            per_char = tokens * (write + read * later_calls) / chars
            results_cost += per_char * chars
            for name, binary in hooks.items():
                removed[name] += per_char * sum(removed_by_hook(binary, cmd, text, home) for _, cmd, text in results)
        previous_output = call_usage.get("output_tokens", 0)
    cost = usage["cost_usd"]
    return results_cost / cost, {name: removed[name] / cost for name in hooks}


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("root", help="a pilot's results directory, holding <model>/raw/<run>")
    p.add_argument("--tasks", default="*", help="task id glob (default: all)")
    p.add_argument("--hook", action="append", default=[], help="name=path of a sobre build to replay")
    args = p.parse_args(argv)
    hooks = dict(h.split("=", 1) for h in args.hook)
    shares, removed = collections.defaultdict(list), collections.defaultdict(list)
    with tempfile.TemporaryDirectory() as home:
        for stream in sorted(glob.glob(f"{args.root}/*/raw/{args.tasks}__native__*/stream.jsonl")):
            run_dir = Path(stream).parent
            got = run_shares(run_dir, hooks, home)
            if got is None:
                continue
            key = (run_dir.parent.parent.name, run_dir.name.split("__")[0])
            shares[key].append(got[0])
            for name, share in got[1].items():
                removed[key + (name,)].append(share)
    for (model, task), values in sorted(shares.items()):
        line = f"{model:7} {task:34} n={len(values):2}  tool results {100 * statistics.median(values):5.1f}% of cost (median)"
        for name in hooks:
            line += f"  {name} removes {100 * statistics.mean(removed[(model, task, name)]):4.1f}%"
        print(line)


if __name__ == "__main__":
    sys.exit(main())
