#!/usr/bin/env python3
"""Token counts and cost of one run, computed from its stream.jsonl.

Tokens per model come from the `result` event's `modelUsage`, which includes subagents.
Claude Code reports cache writes there as one number; the 5-minute / 1-hour split comes
from the per-message `usage.cache_creation` of the assistant events (each API response
counted once: its message id repeats across events). Without a split, writes count as
1-hour writes, the TTL a subscription gets, and a flag says so.

Cost = tokens x harness/prices.json. The client's own estimate, `total_cost_usd`, is
reported next to it as a cross-check.

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
    results = [e for e in events if e.get("type") == "result"]
    return results[-1] if results else None


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
        m["messages"] += 1
        m["input"] += usage.get("input_tokens") or 0
        m["output"] += usage.get("output_tokens") or 0  # a placeholder: the count at message_start
        m["cache_read"] += usage.get("cache_read_input_tokens") or 0
        m["cache_write"] += usage.get("cache_creation_input_tokens") or 0
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


def tokens_by_model(result, msg_usage, flags):
    by_base = {base_model(k): v for k, v in msg_usage.items()}
    out = {}
    if result and result.get("modelUsage"):
        for model, mu in result["modelUsage"].items():
            msgs = msg_usage.get(model) or by_base.get(base_model(model))
            w5, w1 = split_cache_writes(mu.get("cacheCreationInputTokens") or 0, msgs, model, flags)
            out[model] = {
                "input": mu.get("inputTokens") or 0,
                "output": mu.get("outputTokens") or 0,
                "cache_read": mu.get("cacheReadInputTokens") or 0,
                "cache_write_5m": w5,
                "cache_write_1h": w1,
                "client_cost_usd": mu.get("costUSD"),
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


def compute(stream_path, prices_path=DEFAULT_PRICES):
    price_table = json.loads(Path(prices_path).read_text())
    events = read_events(stream_path)
    result = result_event(events)
    flags = []
    by_model, source = tokens_by_model(result, message_usage(events), flags)

    totals = Counter()
    cost = 0.0
    for model, tokens in by_model.items():
        key, price = price_for(model, price_table["models"])
        if price is None:
            flags.append(f"unpriced_model:{model}")
            tokens["cost_usd"] = None
        else:
            tokens["cost_usd"] = sum(tokens[c] * price[c] for c in TOKEN_CLASSES) / 1e6
            cost += tokens["cost_usd"]
        tokens["price_key"] = key
        for c in TOKEN_CLASSES:
            totals[c] += tokens[c]
    if result is None:
        flags.append("no_result_event")

    return {
        "source": source,
        "by_model": by_model,
        "tokens": {c: totals[c] for c in TOKEN_CLASSES},
        "cost_usd": round(cost, 6),
        "client_total_cost_usd": result.get("total_cost_usd") if result else None,
        "num_turns": result.get("num_turns") if result else None,
        "duration_ms": result.get("duration_ms") if result else None,
        "duration_api_ms": result.get("duration_api_ms") if result else None,
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
