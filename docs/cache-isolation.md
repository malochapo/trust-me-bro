# Isolation: the prompt cache that runs share

2026-10-12. An offline study of pilots 1 to 5, with no API spend. Interleaved runs share the prompt cache, and that sharing favored some arms over others. This page shows how much, and what the harness now reports instead.

## What runs share

The prompt cache belongs to the API workspace, not to the key: two keys of one workspace read each other's entries ([Anthropic, prompt caching](https://platform.claude.com/docs/en/build-with-claude/prompt-caching)). Every arm of a pilot bills to its own key, so the console can bill each arm on its own, but the keys share one workspace.

A capture of Claude Code 2.1.296's requests, against a local fake endpoint with no key, shows what a run can share with another. A session's first request holds, in order:

1. the tool definitions (18 built-in tools, about 46,000 characters);
2. three system blocks: a billing header, a one-line identity, and the system prompt, the last two marked for caching;
3. the first user message: the user `CLAUDE.md`, the git status and the task's prompt;
4. a system-role message with the environment, the working directory included, marked for caching.

The working directory is different in every run (`run.py` names it after a hash of the run id), so a run can only find in the cache what comes before it: the tool definitions and the system prompt. For native that is 11,102 tokens. Everything after the first request reads what the run wrote itself. A `CLAUDE.md` does not change the shared part: it goes into the first user message. `--append-system-prompt` changes the system prompt (and the identity line), but not the tool definitions, which come first and are most of the prefix: two runs that differ only by appended text still share them. A tool loaded up front changes the tool definitions, and with them every cache entry of the prefix: the first cache mark comes after all the tools.

## Who found the cache warm

The first request of each session, by arm (`python3 -I harness/cache_isolation.py`):

| Pilot | Arms with native's prefix | lean-ctx | Headroom |
| --- | --- | --- | --- |
| 1, Sonnet | 100% warm (all of them) | 14 of 20 | 16 of 20 |
| 2, Sonnet | 100% warm | 2 of 12 | 3 of 12 |
| 3 and 4, both models | 100% warm | | |
| 5, Haiku | 100% warm | 3 of 12 | 1 of 12 |
| 5, Sonnet | 100% warm | 2 of 6 | 4 of 6 |

- **native, rtk and every sobre arm** start with the same 11,102-token prefix. rtk's hook and `RTK.md`, and sobre's hooks and its deferred MCP server, leave it untouched. Each of these runs found the prefix that the run before it, of any of these arms, had just written.
- **lean-ctx** loads its 59 tools up front (`alwaysLoad`), so its prefix is its own: 15,523 tokens. Only another lean-ctx run warms it.
- **Headroom's** proxy rewrites the prompt; its prefix is 10,183 tokens. Only another Headroom run warms it.

In an interleaved order, five or six arms took turns: native's prefix was rewarmed by almost every run, lean-ctx's and Headroom's only by one run in five or six. A cold start writes the prefix instead of reading it: about $0.027 more per session on Sonnet 5.5 (11,102 tokens at $2.50 instead of $0.10 per million) and $0.0013 on Haiku 5.5. On pilot 1's short Sonnet tasks, where native cost $0.055 a run, that is half a run.

Caching changes only what a request costs, never what the model answers, so the runs themselves are not affected: only their cost depends on the order they ran in.

## The correction

`usage.py` now gives each run a second cost, `cost_cold_usd`: the same run had each of its sessions started with a cold cache. The first response of each session reads, from the cache, only what other runs wrote (or, for a session started the next day, the day before); its cache reads are priced as the cache writes they would have been, at the lifetime the response wrote with. Later responses are unchanged: they read what their own run wrote. A subagent's first response is treated the same way the first time its type runs in a run; a fork starts from its parent's context and is left alone. For runs recorded before the field existed, `report.py`, `pilot4_summary.py` and `cache_isolation.py` compute it from `stream.jsonl`.

`cache_isolation.py` also prices the opposite case, every session warm: where a start missed its arm's prefix, the prefix is priced as read. Cold and warm bracket what a user of either setup would meet, depending on how recently they used it.

## What it changes

Cost relative to Claude Code alone, from the same runs (geometric mean of per-task ratios, 95% bootstrap interval as in each pilot's report):

| Tool | Pilot | Measured | Every session cold | Every session warm |
| --- | --- | --- | --- | --- |
| Headroom | 1, Sonnet | 1.14 (1.06–1.25) | 1.00 (0.97–1.03) | 1.04 (1.00–1.09) |
| Headroom | 2, Sonnet | 1.30 (1.22–1.40) | 0.99 (0.92–1.10) | 1.01 (0.91–1.15) |
| Headroom | 5, Haiku | 0.89 (0.81–1.01) | 0.87 (0.79–0.98) | 0.87 (0.79–0.99) |
| Headroom | 5, Sonnet | 1.11 (0.99–1.21) | 1.07 (0.97–1.16) | 1.09 (0.98–1.17) |
| lean-ctx | 1, Sonnet | 1.62 (1.43–1.82) | 1.40 (1.31–1.49) | 1.40 (1.27–1.53) |
| lean-ctx | 2, Sonnet | 1.81 (1.52–2.11) | 1.35 (1.16–1.58) | 1.31 (1.07–1.61) |
| lean-ctx | 5, Haiku | 1.78 (1.28–2.25) | 1.74 (1.26–2.20) | 1.75 (1.26–2.22) |
| lean-ctx | 5, Sonnet | 1.23 (1.16–1.32) | 1.18 (1.12–1.25) | 1.16 (1.10–1.24) |
| rtk | 1, Sonnet | 1.06 (1.01–1.11) | 1.04 (1.00–1.08) | 1.06 (1.01–1.11) |
| rtk | 2, Sonnet | 1.10 (0.91–1.44) | 1.07 (0.93–1.31) | 1.10 (0.91–1.44) |
| rtk | 5, Haiku | 1.48 (1.21–1.76) | 1.47 (1.20–1.74) | 1.48 (1.21–1.76) |
| rtk | 5, Sonnet | 1.19 (1.05–1.36) | 1.18 (1.05–1.33) | 1.19 (1.05–1.36) |
| sobre 0.1.0-rc.1 | 1, Sonnet | 1.13 (1.04–1.24) | 1.08 (1.02–1.16) | 1.13 (1.04–1.24) |
| sobre 0.1.0-rc.1 | 2, Sonnet | 1.08 (0.96–1.23) | 1.06 (0.97–1.18) | 1.08 (0.96–1.23) |

Pilots 3 and 4 measured sobre's builds only, which all keep native's prefix: their ratios move by 0.01 or less, except the two arms that build a dense index (`sobre-rc3-dense-told`: 1.31 to 1.22 on Haiku). The full table is `cache_isolation.py`'s output.

1. **Headroom costs what Claude Code alone costs on short tasks.** Its overhead on pilots 1 and 2, 14% and 30%, was its runs starting cold. Pilot 2 read it as Headroom writing more to the cache (24,000 tokens per run against 15,000); those writes were mostly its prefix, written at 9 of its 12 starts. On Haiku's long conversations it costs less than native, 0.87, with an interval that now stays under 1 in both normalizations, and its four tasks still disagree.
2. **lean-ctx costs more, but less than published**: 1.31 to 1.40 on pilots 1 and 2 instead of 1.62 and 1.81. Its tools sent with every request are a real fixed cost, which the cold column keeps (its prefix is 4,400 tokens longer than native's); what goes is the cost of writing that prefix at most of its starts.
3. **rtk and sobre do not move**: they share native's prefix, so all three were warm together.
4. **Long conversations change little**: one session start is a small part of a run that makes 30 to 70 calls.

The acquis about fixed costs still holds, in a narrower form: a tool that sends its own tools with every request pays for them on every call, and pays to write them once per session, but a proxy that only rewrites tool results does not cost more than Claude Code alone on these tasks.

## Why not isolate the runs themselves

The cost a run would have had on a cold cache is exact from its own tokens: the first response of a session reports the tokens it read, and a cold start would have written exactly those. Isolating on the API side instead has costs of its own:
- **one workspace per arm** keeps arms apart, but each arm is then warmed by its own runs only, and how often depends on its place in the order and the length of its runs;
- **a per-run marker in the shared prefix** (an inert tool, the only part of the prefix a run controls) would start every run cold, but adds a tool the agent sees in every arm.

So the harness keeps the interleaved order and reports both costs. `report.py`'s paired table adds a cold-start ratio next to the measured one, `pilot4_summary.py` a column, and the README's headline uses the cold-start ratios.

## Limits

- **Requests the stream does not show.** A request with no assistant message in `stream.jsonl` (none appeared in the capture of a `-p` run) is counted in the totals but cannot be repriced.
- **Subagents.** No run of pilots 1 to 5 started one. The rule above assumes every subagent of a type shares a prefix across runs; a later spawn of the same type, more than five minutes after the first, would have started cold too and is not repriced.
- **Lifetime.** A start is repriced at the lifetime it wrote with. Every run of pilots 1 to 5 wrote 5-minute entries, an API key's default.
- **The warm column** takes each arm's prefix to be the most common non-zero first read of its sessions.

## Reproduce

```sh
python3 -I harness/cache_isolation.py                          # the tables above
python3 -I harness/report.py --raw results/pilot2/raw --out results/pilot2   # cold-start ratio per arm
python3 -I harness/pilot4_summary.py --pilot pilot5      # pilot 5 by part, with a cold-start column
```
