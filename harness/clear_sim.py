#!/usr/bin/env python3
"""What clearing old tool results (the API's clear_tool_uses_20250919 context edit) would change in
the cost of recorded runs, on the same path.

Per API call the stream gives cache reads, cache writes and uncached input. A tool result added
before call k sits at prompt position ~ the cache reads of call k. The policy: when the prompt
exceeds TRIGGER, clear every result but the last KEEP, if that frees at least CLEAR_AT_LEAST
tokens; a cleared result leaves a placeholder of PLACEHOLDER tokens. A clearing invalidates the
cache from the first newly cleared result on, so that call writes the rest of the prompt again.

A result's tokens are its share of the call's new tokens, capped at --tokens-per-char times its
characters: the stream's per-call output counts are partial, so the new tokens also hold part of
the previous answer, and a cache miss rewrites the whole prompt. The result moves with the cap
(see docs/clearing.md). The figure is the direct effect: it cannot see what the agent would do
without the cleared outputs, such as running a command again.

Usage: python3 -I harness/clear_sim.py results/pilot4 [--tokens-per-char 0.42]
       python3 -I harness/clear_sim.py --transcript ~/.claude/projects/<project>/<session>.jsonl
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # -I leaves the script dir off sys.path

import argparse
import collections
import glob
import json
import statistics

import common

PRICES = json.loads((common.BENCH_ROOT / "harness" / "prices.json").read_text())["models"]
PLACEHOLDER = 12
POLICIES = [(30000, 3, 5000), (50000, 3, 10000), (50000, 5, 10000), (100000, 3, 20000)]
CONVERSATION = ("mt-", "long-", "xs-")


def result_chars(block):
    content = block.get("content")
    text = content if isinstance(content, str) else "".join(
        x.get("text", "") for x in (content or []) if isinstance(x, dict))
    return len(text)


def calls_of(path, transcript=False):
    """API calls in order: {usage, segment, result sizes in chars added before the call}. A segment
    is a session in a bench stream, the span between two compactions in a transcript."""
    calls, by_id, pending, segment, output = [], {}, [], None, {}
    for line in open(path):
        try:
            event = json.loads(line)
        except ValueError:
            continue
        kind = event.get("type")
        if kind == "system" and event.get("subtype") == ("compact_boundary" if transcript else "init"):
            segment = event.get("session_id") if not transcript else (segment or 0) + 1
        elif kind == "assistant":
            message = event["message"]
            if transcript and not str(message.get("model", "")).startswith("claude-"):
                continue
            usage = message.get("usage") or {}
            if message.get("id") not in by_id:
                by_id[message.get("id")] = len(calls)
                calls.append({"usage": usage, "segment": segment, "results": pending, "model": message.get("model")})
                pending = []
            elif usage:
                calls[by_id[message["id"]]]["usage"] = usage
            output[message.get("id")] = max(output.get(message.get("id"), 0), usage.get("output_tokens", 0))
        elif kind == "user" and isinstance(event.get("message", {}).get("content"), list):
            pending += [result_chars(b) for b in event["message"]["content"]
                        if isinstance(b, dict) and b.get("type") == "tool_result"]
    return calls, sum(output.values())


def unit_prices(model, ttl="5m"):
    """$ per token, Haiku's long-prompt prices from their threshold on. A model missing from the
    price table is priced in input units with the ratios of models before the 5.5 family (cache
    read 0.1, write 1.25 for 5 minutes and 2 for an hour, output 5)."""
    if model not in PRICES:
        flat = {"input": 1.0, "output": 5.0, "cache_read": 0.1, "cache_write": 2.0 if ttl == "1h" else 1.25}
        return lambda prompt: flat
    p = PRICES[model]

    def at(prompt):
        q = p["long_prompt"] if "long_prompt" in p and prompt > p["long_prompt"]["over_tokens"] else p
        return {"input": q["input"] / 1e6, "output": q["output"] / 1e6,
                "cache_read": q["cache_read"] / 1e6, "cache_write": q[f"cache_write_{ttl}"] / 1e6}
    return at


def input_cost(calls, prices, tokens_per_char, policy=None):
    """The run's input-side cost; with no policy, as recorded."""
    trigger, keep, clear_at_least = policy or (None, 0, 0)
    total, previous_output, segment, results, cleared = 0.0, 0, object(), [], 0
    for call in calls:
        usage = call["usage"]
        if call["segment"] != segment:
            segment, results, cleared, previous_output = call["segment"], [], 0, 0
        read, write, uncached = (usage.get("cache_read_input_tokens", 0),
                                 usage.get("cache_creation_input_tokens", 0), usage.get("input_tokens", 0))
        chars = sum(call["results"])
        if chars:
            tokens = min(max(write + uncached - previous_output, 0) * chars / (chars + 200), chars * tokens_per_char)
            position = read
            for n in call["results"]:
                results.append([position, tokens * n / chars, False])
                position += tokens * n / chars
        prompt = read + write + uncached - cleared
        read = max(read - cleared, 0)
        if trigger is not None and prompt > trigger:
            candidates = [r for r in (results[:-keep] if keep else results) if not r[2]]
            freed = sum(max(r[1] - PLACEHOLDER, 0) for r in candidates)
            if candidates and freed >= clear_at_least:
                first = min(r[0] for r in candidates)
                first -= sum(max(r[1] - PLACEHOLDER, 0) for r in results if r[2] and r[0] < first)
                for r in candidates:
                    r[2] = True
                cleared += freed
                prompt -= freed
                read = max(min(first, prompt - uncached), 0)
                write = max(prompt - uncached - read, 0)
        p = prices(prompt)
        total += read * p["cache_read"] + write * p["cache_write"] + uncached * p["input"]
        previous_output = usage.get("output_tokens", 0)
    return total


def bench(root, tokens_per_char):
    ratios = collections.defaultdict(lambda: collections.defaultdict(list))
    for stream in sorted(glob.glob(f"{root}/*/raw/*__native__*/stream.jsonl")):
        run_dir = Path(stream).parent
        usage = common.read_json(run_dir / "usage.json") or {}
        model = next(iter(usage.get("by_model", {})), None)
        if model not in PRICES:
            continue
        calls, _ = calls_of(stream)
        prices = unit_prices(model)
        output = usage["tokens"]["output"] * PRICES[model]["output"] / 1e6  # clearing leaves it alone
        base = input_cost(calls, prices, tokens_per_char) + output
        task = run_dir.name.split("__")[0]
        key = (run_dir.parent.parent.name, "conversation" if task.startswith(CONVERSATION) else "one message")
        ratios[key]["check"].append(usage["cost_usd"] / base)
        for policy in POLICIES:
            ratios[key][policy].append((input_cost(calls, prices, tokens_per_char, policy) + output) / base)
    for (model, kind), by in sorted(ratios.items()):
        print(f"{model} {kind}: n={len(by['check'])}, recorded/simulated cost {statistics.median(by['check']):.2f}")
        for policy in POLICIES:
            v = by[policy]
            print(f"   trigger {policy[0]:>6} keep {policy[1]} clear_at_least {policy[2]:>5}: "
                  f"cost ratio median {statistics.median(v):.3f}, mean {statistics.mean(v):.3f}, min {min(v):.3f}")


def transcript(path, tokens_per_char):
    calls, output_tokens = calls_of(path, transcript=True)
    model = collections.Counter(c["model"] for c in calls).most_common(1)[0][0]
    one_hour = sum((c["usage"].get("cache_creation") or {}).get("ephemeral_1h_input_tokens", 0) for c in calls)
    ttl = "1h" if one_hour > sum(c["usage"].get("cache_creation_input_tokens", 0) for c in calls) / 2 else "5m"
    prices = unit_prices(model, ttl)
    output = output_tokens * prices(0)["output"]
    base = input_cost(calls, prices, tokens_per_char) + output
    prompts = [sum(c["usage"].get(k, 0) for k in ("cache_read_input_tokens", "cache_creation_input_tokens",
                                                   "input_tokens")) for c in calls]
    priced = model if model in PRICES else f"{model} (not in the price table: cache read 0.1x input)"
    print(f"{priced}, {ttl} cache; {len(calls)} calls, median prompt {statistics.median(prompts):.0f} tokens, "
          f"max {max(prompts)}, output {output / base:.1%} of cost")
    for policy in POLICIES:
        print(f"   trigger {policy[0]:>6} keep {policy[1]} clear_at_least {policy[2]:>5}: "
              f"cost ratio {(input_cost(calls, prices, tokens_per_char, policy) + output) / base:.3f}")


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("root", nargs="?", help="a pilot's results directory, holding <model>/raw/<run>")
    p.add_argument("--transcript", help="a Claude Code transcript (.jsonl) instead of bench runs")
    p.add_argument("--tokens-per-char", type=float, default=0.42,
                   help="cap on a result's tokens per character (default 0.42, see docs/clearing.md)")
    args = p.parse_args(argv)
    if args.transcript:
        transcript(args.transcript, args.tokens_per_char)
    elif args.root:
        bench(args.root, args.tokens_per_char)
    else:
        p.error("give a results directory or --transcript")


if __name__ == "__main__":
    sys.exit(main())
