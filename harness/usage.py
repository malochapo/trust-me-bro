#!/usr/bin/env python3
"""Token counts and cost of one run, computed from its stream.jsonl.

Tokens per model come from the `result` events' `modelUsage`, which includes subagents.
A multi-turn run resumes the session once per turn, and each turn ends with its own
`result` event. A resumed session carries its counters over: each event's `modelUsage`,
`total_cost_usd` and `duration_api_ms` are the session's running totals, so the last event
of a session holds all of it (`num_turns` and `duration_ms` are per turn, and are summed).
A run that starts a new session sums its sessions, told apart by `session_id`.
Claude Code reports cache writes there as one number; the 5-minute / 1-hour split comes
from the per-message `usage.cache_creation` of the assistant events (each API response
counted once: its message id repeats across events). Without a split, writes count as
1-hour writes, the TTL a subscription gets, and a flag says so.

Cost = tokens x harness/prices.json. A model priced by prompt length (Haiku 5.5 over 100K
tokens) has its long-prompt share of each token class taken from the assistant events: the
input, cache read and cache write tokens of its requests over the threshold, and for output,
the share of those requests. The client's own estimate, `total_cost_usd`, is reported next
to it as a cross-check.

The prompt cache is shared by every key of an API workspace, so a run can start on a prefix
another run wrote: Claude Code's tool definitions and system prompt, the same in every run of
a given setup. `cost_cold_usd` is the run's cost had each session started with a cold cache
(see cold_start and docs/cache-isolation.md); it does not depend on which runs came before.

Usage: python3 -I harness/usage.py <run dir | stream.jsonl> [--prices FILE]
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # -I leaves the script dir off sys.path

import argparse
import json
import re
from collections import Counter

from common import BENCH_ROOT

DEFAULT_PRICES = BENCH_ROOT / "harness" / "prices.json"
TOKEN_CLASSES = ["input", "output", "cache_read", "cache_write_5m", "cache_write_1h"]
LONG_PROMPT_THRESHOLDS = (100_000,)  # the thresholds harness/prices.json uses


def read_events(path):
    events = []
    for line in Path(path).read_text(errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if isinstance(event, dict):
            events.append(event)
    return events


def init_event(events):
    return next((e for e in events if e.get("type") == "system" and e.get("subtype") == "init"), None)


def result_event(events):
    results = result_events(events)
    return results[-1] if results else None


def result_events(events):
    return [e for e in events if e.get("type") == "result"]


def message_usage(events):
    """Usage of each API response, counted once, summed per model (main loop and subagents)."""
    seen, by_model = set(), {}
    for event in events:
        if event.get("type") != "assistant":
            continue
        msg = event.get("message") or {}
        usage, msg_id, model = msg.get("usage"), msg.get("id"), msg.get("model") or "unknown"
        if not usage or not msg_id or msg_id in seen or model == "<synthetic>":
            continue
        seen.add(msg_id)
        m = by_model.setdefault(model, Counter())
        prompt = Counter(input=usage.get("input_tokens") or 0,
                         cache_read=usage.get("cache_read_input_tokens") or 0,
                         cache_write=usage.get("cache_creation_input_tokens") or 0)
        m["messages"] += 1
        m["output"] += usage.get("output_tokens") or 0  # a placeholder: the count at message_start
        m.update(prompt)
        # Kept per prompt length, for models priced by it.
        for threshold in LONG_PROMPT_THRESHOLDS:
            if sum(prompt.values()) > threshold:
                m[f"over_{threshold}_messages"] += 1
                for k, v in prompt.items():
                    m[f"over_{threshold}_{k}"] += v
        split = usage.get("cache_creation")
        if isinstance(split, dict):
            m["split_5m"] += split.get("ephemeral_5m_input_tokens") or 0
            m["split_1h"] += split.get("ephemeral_1h_input_tokens") or 0
    return by_model


def base_model(model):
    return re.sub(r"\[.*\]$", "", model)  # "claude-sonnet-5-5[1m]" -> "claude-sonnet-5-5"


def split_cache_writes(total, msgs, model, flags):
    s5 = msgs["split_5m"] if msgs else 0
    s1 = msgs["split_1h"] if msgs else 0
    if s5 + s1 == 0:
        if total:
            flags.append(f"cache_write_split_assumed_1h:{model}")
        return 0, total
    w5 = round(total * s5 / (s5 + s1))
    return w5, total - w5


def running_total(values):
    """The total of a counter that each turn of a resumed session reports as a running total.
    A value below the one before means the count started again, so that value adds to what
    came before."""
    total = previous = 0
    for value in values:
        total += value - previous if value >= previous else value
        previous = value
    return total


def by_session(results):
    """The result events grouped by session, in the order the sessions started."""
    sessions = {}
    for result in results:
        sessions.setdefault(result.get("session_id"), []).append(result)
    return list(sessions.values())


def session_total(results, value):
    """The total over the run of a counter each session reports as a running total."""
    return sum(running_total([value(r) for r in session]) for session in by_session(results))


def tokens_by_model(results, msg_usage, flags):
    by_base = {base_model(k): v for k, v in msg_usage.items()}
    summed = {}
    keys = ("inputTokens", "outputTokens", "cacheReadInputTokens", "cacheCreationInputTokens", "costUSD")
    models = dict.fromkeys(m for r in results for m in (r.get("modelUsage") or {}))
    for model in models:
        summed[model] = Counter()
        for session in by_session(results):
            reports = [r["modelUsage"][model] for r in session if model in (r.get("modelUsage") or {})]
            for key in keys:
                summed[model][key] += running_total([mu.get(key) or 0 for mu in reports])
    out = {}
    if summed:
        for model, mu in summed.items():
            msgs = msg_usage.get(model) or by_base.get(base_model(model))
            w5, w1 = split_cache_writes(mu["cacheCreationInputTokens"], msgs, model, flags)
            out[model] = {
                "input": mu["inputTokens"],
                "output": mu["outputTokens"],
                "cache_read": mu["cacheReadInputTokens"],
                "cache_write_5m": w5,
                "cache_write_1h": w1,
                "client_cost_usd": round(mu["costUSD"], 6),
            }
        return out, "modelUsage"
    flags.append("no_model_usage: tokens from assistant messages, output tokens are placeholders")
    for model, m in msg_usage.items():
        w5, w1 = split_cache_writes(m["cache_write"], m, model, flags)
        out[model] = {"input": m["input"], "output": m["output"], "cache_read": m["cache_read"],
                      "cache_write_5m": w5, "cache_write_1h": w1, "client_cost_usd": None}
    return out, "messages"


def price_for(model, prices):
    """Exact price key, else the longest key the model id starts with (dated ids)."""
    base = base_model(model)
    if base in prices:
        return base, prices[base]
    keys = [k for k in prices if base.startswith(k)]
    if not keys:
        return None, None
    key = max(keys, key=len)
    return key, prices[key]


def content_chars(content):
    if isinstance(content, str):
        return len(content)
    if isinstance(content, list):
        return sum(len(b.get("text") or "") for b in content if isinstance(b, dict) and b.get("type") == "text")
    return 0


def tool_stats(events):
    calls, call_ids, results = Counter(), set(), {}
    for event in events:
        content = (event.get("message") or {}).get("content")
        if not isinstance(content, list):
            continue
        for block in content:
            if not isinstance(block, dict):
                continue
            if event.get("type") == "assistant" and block.get("type") == "tool_use":
                if block.get("id") not in call_ids:
                    call_ids.add(block.get("id"))
                    calls[block.get("name")] += 1
            elif event.get("type") == "user" and block.get("type") == "tool_result":
                results[block.get("tool_use_id")] = block
    return {
        "tool_calls": dict(sorted(calls.items())),
        "tool_calls_total": sum(calls.values()),
        "tool_results": len(results),
        "tool_result_errors": sum(1 for b in results.values() if b.get("is_error")),
        "tool_result_chars": sum(content_chars(b.get("content")) for b in results.values()),
    }


SUBAGENT_TOOLS = ("Agent", "Task")


def session_starts(events):
    """(model, usage) of the API responses a cold cache would have priced differently: the
    first response of each main-loop session, and the first response of each subagent type's
    first spawn. Whatever those responses read from the cache, another run wrote it (or, for a
    session started the next day, the day before). Every later response reads only what its
    own run wrote: a resumed turn keeps its session, a later spawn of a type finds what the
    first one wrote, and a fork (subagent_type "fork") starts from its parent's context."""
    seen, started, kinds, starts = set(), set(), {}, []
    for event in events:
        if event.get("type") != "assistant":
            continue
        msg = event.get("message") or {}
        for block in msg.get("content") or []:
            if isinstance(block, dict) and block.get("type") == "tool_use" and block.get("name") in SUBAGENT_TOOLS:
                kinds[block.get("id")] = (block.get("input") or {}).get("subagent_type") or "general-purpose"
        usage, msg_id, model = msg.get("usage"), msg.get("id"), msg.get("model")
        if not usage or not msg_id or msg_id in seen or model in (None, "<synthetic>"):
            continue
        seen.add(msg_id)
        parent = event.get("parent_tool_use_id")
        if parent is None:
            key = ("session", event.get("session_id"))
        else:
            kind = kinds.get(parent, "unknown")
            if kind == "fork":
                continue
            key = ("subagent", kind)
        if key not in started:
            started.add(key)
            starts.append((model, usage))
    return starts


def cold_start(events, price_table):
    """The run's extra cost had each session started with a cold prompt cache: what each start
    read from the cache is priced as the cache write it would have been, at the lifetime the
    start wrote with (5 minutes, or 1 hour when it wrote 1-hour entries only). Interleaved arms
    share the cache when their keys share a workspace: an arm that keeps native's prompt prefix
    (a hook, a CLAUDE.md) finds it warm at almost every start, and one that changes it (tools
    loaded up front, a proxy that rewrites the prompt) does not. Pricing every start cold makes
    a run's cost independent of the runs before it."""
    extra, read, unpriced = 0.0, 0, set()
    starts = session_starts(events)
    for model, u in starts:
        tokens = u.get("cache_read_input_tokens") or 0
        if not tokens:
            continue
        _, price = price_for(model, price_table["models"])
        if price is None:
            unpriced.add(model)
            continue
        long = price.get("long_prompt")
        prompt = tokens + (u.get("input_tokens") or 0) + (u.get("cache_creation_input_tokens") or 0)
        if long and prompt > long["over_tokens"]:
            price = long
        split = u.get("cache_creation") or {}
        hour_only = (split.get("ephemeral_1h_input_tokens") or 0) and not (split.get("ephemeral_5m_input_tokens") or 0)
        write = "cache_write_1h" if hour_only else "cache_write_5m"
        extra += tokens * (price[write] - price["cache_read"]) / 1e6
        read += tokens
    return {"starts": len(starts), "cache_read_tokens": read, "extra_usd": round(extra, 6),
            "unpriced_models": sorted(unpriced)}


def cold_cost(run_dir, run_usage, prices_path=DEFAULT_PRICES):
    """`cost_cold_usd` of a run: from its usage.json, or, for a run recorded before that field
    existed, from its stream. None without a cost or a stream."""
    if run_usage.get("cost_cold_usd") is not None:
        return run_usage["cost_cold_usd"]
    stream = Path(run_dir) / "stream.jsonl"
    if run_usage.get("cost_usd") is None or not stream.exists():
        return None
    cold = cold_start(read_events(stream), json.loads(Path(prices_path).read_text()))
    return round(run_usage["cost_usd"] + cold["extra_usd"], 6)


def long_prompt_shares(msgs, threshold):
    """Share of each token class spent in requests whose prompt is over `threshold`."""
    if not msgs or not msgs["messages"]:
        return {c: 0.0 for c in TOKEN_CLASSES}
    def share(key):
        total = msgs[key]
        return msgs[f"over_{threshold}_{key}"] / total if total else 0.0
    write = share("cache_write")
    return {"input": share("input"), "cache_read": share("cache_read"),
            "cache_write_5m": write, "cache_write_1h": write,
            "output": msgs[f"over_{threshold}_messages"] / msgs["messages"]}


def price_tokens(tokens, price, msgs):
    """Cost in USD of one model's tokens, with its long-prompt prices when it has them."""
    long = price.get("long_prompt")
    if not long:
        return sum(tokens[c] * price[c] for c in TOKEN_CLASSES) / 1e6, None
    if long["over_tokens"] not in LONG_PROMPT_THRESHOLDS:
        raise SystemExit(f"prices.json: long_prompt.over_tokens {long['over_tokens']} is not tracked")
    shares = long_prompt_shares(msgs, long["over_tokens"])
    cost = sum(tokens[c] * ((1 - shares[c]) * price[c] + shares[c] * long[c]) for c in TOKEN_CLASSES) / 1e6
    return cost, {c: round(v, 4) for c, v in shares.items()}


def compute(stream_path, prices_path=DEFAULT_PRICES):
    price_table = json.loads(Path(prices_path).read_text())
    events = read_events(stream_path)
    results = result_events(events)
    result = results[-1] if results else None
    flags = []
    msg_usage = message_usage(events)
    by_model, source = tokens_by_model(results, msg_usage, flags)
    by_base = {base_model(k): v for k, v in msg_usage.items()}

    totals = Counter()
    cost = 0.0
    for model, tokens in by_model.items():
        key, price = price_for(model, price_table["models"])
        if price is None:
            flags.append(f"unpriced_model:{model}")
            tokens["cost_usd"] = None
        else:
            msgs = msg_usage.get(model) or by_base.get(base_model(model))
            tokens["cost_usd"], shares = price_tokens(tokens, price, msgs)
            if shares is not None:
                tokens["long_prompt_shares"] = shares
            cost += tokens["cost_usd"]
        tokens["price_key"] = key
        for c in TOKEN_CLASSES:
            totals[c] += tokens[c]
    if result is None:
        flags.append("no_result_event")
    cold = cold_start(events, price_table)

    return {
        "source": source,
        "by_model": by_model,
        "tokens": {c: totals[c] for c in TOKEN_CLASSES},
        "cost_usd": round(cost, 6),
        "cost_cold_usd": round(cost + cold["extra_usd"], 6),
        "cold_start": cold,
        "client_total_cost_usd": round(session_total(results, lambda r: r.get("total_cost_usd") or 0), 6) if results else None,
        "num_turns": sum(r.get("num_turns") or 0 for r in results) if results else None,
        "duration_ms": sum(r.get("duration_ms") or 0 for r in results) if results else None,
        "duration_api_ms": session_total(results, lambda r: r.get("duration_api_ms") or 0) if results else None,
        "conversation_turns": len(results),
        "result_subtype": result.get("subtype") if result else None,
        "is_error": result.get("is_error") if result else None,
        **tool_stats(events),
        "flags": flags,
        "prices": {"source": price_table.get("source"), "as_of": price_table.get("as_of")},
    }


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("path", help="run directory or stream.jsonl")
    p.add_argument("--prices", default=str(DEFAULT_PRICES))
    args = p.parse_args(argv)
    path = Path(args.path)
    stream = path / "stream.jsonl" if path.is_dir() else path
    print(json.dumps(compute(stream, args.prices), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
