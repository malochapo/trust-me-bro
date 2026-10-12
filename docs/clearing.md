# Clearing old tool results: what it could save on Claude Code

2026-10-12. An offline study, with no API spend: would clearing old tool results from the prompt lower a run's cost, and does anything do it already?

## Why look at it

A tool result is written to the prompt cache once, then read again at every later API call of the session. In pilot 4's native runs, tool results account for 28% of the cost of one-message tasks and 36% to 50% of conversations (`harness/result_share.py`). Compression at the source moves little, because agents already filter their outputs: sobre's hook removes about 1% of the cost (pilot 4, part D). The other way to shrink that share is to drop old results once they have served. The API has a context edit for it, `clear_tool_uses_20250919` (beta `context-management-2025-06-27`): past a trigger, results older than the last few are replaced by a placeholder. Each clearing breaks the prompt cache from the first cleared result on, so the rest of the prompt is written again.

## Method

`harness/clear_sim.py` replays the recorded API calls of native runs and prices them with and without a clearing policy, on the same path. It reads cache reads, cache writes and uncached input per call from the stream, places each result at the position where it entered the prompt, and charges the rewrite that each clearing causes. Output is priced from `usage.json` and does not change. With no policy, the simulated cost matches the recorded one (median ratio 1.00).

One quantity is uncertain: a result's size in tokens. The stream's per-call output counts are partial, so a call's new tokens also contain part of the previous answer, and a cache miss rewrites the whole prompt. The simulation caps a result at a number of tokens per character. On Claude Code transcripts, where per-call output counts are complete, results measure 0.42 tokens per character (median over 1,281 large results; 0.46 over 2,903 in subagent transcripts). In the bench streams, the uncorrected figure is 0.57 (Haiku) and 0.51 (Sonnet), which still includes part of the previous answer. The default cap is 0.42. Without a cap, the simulation credited Haiku with a 14% saving. Most of that came from the inflated sizes.

What the simulation cannot see is what the agent does without the cleared outputs: running a command again or reading a file again costs a new result. The figures are an upper bound for the policy's direct effect.

## Results

Cost ratio to the recorded run (median over runs), policy `trigger 50,000 tokens, keep 3, clear_at_least 10,000`:

| Runs | n | cap 0.33 | cap 0.42 | cap 0.50 |
|---|---|---|---|---|
| pilot 4, Haiku conversations | 32 | 0.99 | 0.95 | 0.91 |
| pilot 4, Sonnet conversations | 28 | 1.00 | 1.00 | 1.00 |
| pilot 3, Haiku conversations | 8 | | 1.00 | |
| pilot 3, Sonnet conversations | 12 | | 1.00 | |
| one-message tasks, both models | 30 | | 1.00 | |
| one long Claude Code session (10,883 calls, 1M-token context) | 1 | 0.75 | 0.70 | 0.68 |

Other policies (trigger 30,000 to 100,000, keep 3 or 5) give the same picture. A 30,000 trigger costs more on Sonnet (median 1.06), because it clears in runs too short to pay back the rewrite.

What decides it is how many calls follow a clearing. Haiku's conversations make twice as many calls as Sonnet's (median 26 to 53 against 16 to 34) with larger prompts (median 36,000 to 69,000 tokens against 26,000 to 45,000). Sonnet's runs end before a cleared result has been skipped often enough to pay for the rewrite. The bench's tasks are short next to real sessions. The long session in the last row, which ran these pilots, has a median prompt of 420,000 tokens. There, clearing would cut about 30% of the cost on the same path. Haiku's long-prompt prices (over 100,000 tokens) play no part: 4 of the 32 Haiku runs have a call over that threshold, and simulating without those prices gives the same ratios.

## Claude Code already clears

A local capture of Claude Code 2.1.296's requests, against a fake endpoint with no key, shows a `context_management` field in every request. It holds one edit, `clear_thinking_20251015` with `keep: all`, and no tool clearing. The binary also contains:

- a `clear_tool_uses_20250919` edit sent when a session resumes after being idle, when the cache has expired and a rewrite costs nothing extra. It sits behind a rollout setting (`off`, `shadow`, on);
- a client-side "time-based microcompact" that replaces old tool results, keeps the most recent ones and saves the originals to disk.

In the long session above, the prompt shrank seven times without a compaction (for example from 772,619 to 447,159 tokens), each time with a cache miss. Claude Code thus clears when clearing is cheap, and its auto-compaction bounds the prompt otherwise. A proxy that added its own `clear_tool_uses` edit would duplicate a mechanism the host is still tuning, and could conflict with it.

## sobre's proxy prunes nothing with Claude Code

sobre's proxy shortens old tool results in the history (`rust/src/proxy/history_prune.rs`) but never inside the prefix the client has marked with `cache_control`, to keep the cache valid. Claude Code marks its last message in every request (seen in the capture), so the protected prefix is the whole conversation and the pruning never runs. With OpenAI clients, which send no marker, it runs. No bench run has used sobre's proxy.

## What would measure it

A live test needs sessions long enough for clearing to pay: well past the bench's conversations (hundreds of calls, prompts over 150,000 tokens), at several dollars per Sonnet run. On the bench's task lengths, the expected effect (0 to 5%) is below the run-to-run spread, so a live run there would decide nothing.
