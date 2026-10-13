# MCP tools the agent does not see

2026-10-12. Across pilots 1 to 4, 454 runs had sobre's MCP server connected and no instruction about it, and no agent called a sobre tool ([pilot 4](pilot-4.md)). That finding has two possible causes: the agent sees the tools and has no use for them, or it does not see them. This page shows the second is real, adds the arms that tell the two apart, and runs them: loaded up front, the tools are used on short search questions and seldom in long sessions, and either way the run costs more for the same answers.

## What Claude Code sends

A capture of Claude Code 2.1.296's requests against a local fake endpoint, with a two-tool MCP server and tool search on (`ENABLE_TOOL_SEARCH=true`; Claude Code turns tool search off for a custom base URL unless it is set, as [arms/README.md](../arms/README.md) notes for Headroom):

| Server config | What the first request's `tools` holds |
| --- | --- |
| default | 12 tools: the built-ins Claude Code keeps loaded, `ToolSearch`, and a `defer_loading` placeholder. The MCP tools are not there; the environment message lists their names. |
| `"alwaysLoad": true` | the same, plus both MCP tools with their full definitions |

The `system/init` event lists the MCP tools in both cases, so a run's `meta.json` cannot tell them apart; the arm's `mcp.json` can.

In pilots 1 to 4, sobre's server was registered as `sobre init` writes it, without `alwaysLoad`: its 15 tools were deferred, and the agent saw only their names. The 75 `ToolSearch` calls of those pilots are all in the `-told` arms, whose `CLAUDE.md` named the tools. lean-ctx sets `alwaysLoad` itself, and its agents did call its tools; lean-ctx also denies Grep and Glob, so those runs cannot isolate visibility either.

## The arms

- `sobre-rc2-mcp-always`: `sobre-rc2-mcp`, with its server marked `alwaysLoad`.
- `sobre-rc3-dense-always`: `sobre-rc3-dense`, the same.

`arms/lib.sh`'s `finish_setup '<env>' always-load` marks every server of the arm's `mcp.json`. `run.py` records which servers load up front (`meta.json`, `mcp_always_load`), and marks a run invalid when an arm named `*-always` has a server that does not. These arms are not vendor setups: they ask a question about the agent, not about sobre.

## The tests

2026-10-13, with pilot 4's settings and fixture (`build/pilot2`, HEAD `51546e1`), effort `medium`, arms interleaved, three runs at a time:

| Test | Tasks | Arms | Runs | Spend |
| --- | --- | --- | --- | --- |
| Haiku 5.5, search | pilot 4's part C: five questions worded by behaviour, not by the code's words | `native`, `sobre-rc2-mcp` (tools deferred, as in pilots 1 to 4), `sobre-rc2-mcp-always`, `sobre-rc3-dense-always` | 60 | $0.24 |
| Sonnet 5.5, search | the same | `native`, `sobre-rc2-mcp-always` | 30 | $1.30 |
| Haiku 5.5, long sessions | pilot 4's part A: seven messages over two unrelated investigations, with a `/compact` between them, 45-minute limit | `native`, `sobre-rc2-mcp-always` | 12 | $0.78 |

Three repetitions each. Every run was valid and billed to its arm's key. One smoke run per new arm and model cost $0.10 more (`results/mcp-always/smoke*/`). The paired reports are [results/mcp-always/haiku/report.md](../results/mcp-always/haiku/report.md) (both Haiku tests) and [results/mcp-always/sonnet/report.md](../results/mcp-always/sonnet/report.md).

## Results

| Test | Arm | Runs that called sobre | sobre calls per run | Success | Turns | Cost vs native | Cold start |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Haiku, search | `native` | 0/15 | 0 | 15/15 | 5.8 | 1 | 1 |
| | `sobre-rc2-mcp`, deferred | 0/15 | 0 | 14/15 | 5.4 | 0.98 (0.88–1.11) | 0.98 (0.91–1.07) |
| | `sobre-rc2-mcp-always` | 15/15 | 3.3 | 15/15 | 6.3 | 1.43 (1.17–1.67) | 1.32 (1.22–1.41) |
| | `sobre-rc3-dense-always` | 15/15 | 3.9 | 15/15 | 6.2 | 1.24 (1.00–1.53) | 1.20 (1.09–1.32) |
| Sonnet, search | `native` | 0/15 | 0 | 15/15 | 4.3 | 1 | 1 |
| | `sobre-rc2-mcp-always` | 13/15 | 3.1 | 15/15 | 5.7 | 1.32 (1.17–1.46) | 1.40 (1.31–1.50) |
| Haiku, long sessions | `native` | 0/6 | 0 | 6/6 | 65.8 | 1 | 1 |
| | `sobre-rc2-mcp-always` | 3/6 | 1.0 | 5/6 | 63.3 | 1.06 (1.03–1.09) | 1.06 (1.03–1.09) |

Cost: geometric mean of per-task cost ratios, 95% bootstrap interval over tasks (five for search, two for long sessions, where the interval says little).

1. **The agents had not seen the tools.** Deferred, no run called sobre, as in the 454 runs before. Loaded up front, every Haiku search run and 13 of 15 Sonnet ones did, with no instruction about them, and each began with them. Haiku called `sobre_compose` once, then sobre's regex search and its file reader where native uses grep and `sed` in a shell; Sonnet went straight to the search and the reader. Shell calls per run fell from 4.7 to 1.7 (Haiku, rc.2) and 0.4 (rc.3), and from 3.1 to 0.5 (Sonnet).
2. **On search questions, they cost more for the same answers.** Every run of the visible arms succeeded, and a run cost 1.20 to 1.40 times native's with a cold cache. Most of that is the tools themselves: their definitions add about 6,900 tokens to every request (24,256 tokens in Haiku's first request, against 17,345), written once and read at every call. Priced that way, they make $0.0012 of Haiku rc.2's $0.0015 extra per run and all of rc.3's, and $0.020 of Sonnet's $0.026; the rest of the run costs what native's does, within 7% on Haiku and 10% on Sonnet.
3. **In long sessions, the tools were left aside, and still paid for.** Over 6 runs and 338 tool calls, the agent called sobre 6 times, always `sobre_compose`, twice in each security review and never in the log investigation, where it ran tests and read logs in the shell as native does. The run cost 1.06 times native's, about what the definitions cost on their own (+7%, from their size and the number of requests). One request of one run went past Haiku 5.5's 100,000-token price tier, which the 6,900 tokens make more likely. The one failure is a recap that left out two of the routes found before the compaction.
4. **No agent searched by meaning.** The search questions are worded so that the code's words do not match them, which is what sobre's semantic search is for. It was never called: every search was by regular expression (and one by symbol). The visible tools replaced grep; they did not change how the agent looks for code.
5. **rc.2 against rc.3.** The dense build's arm cost less on Haiku's search questions, but the intervals overlap and its agents did not use what the dense build adds.

So the finding becomes narrower and firmer: agents do not use an MCP server's tools that Claude Code defers. Loaded up front, Haiku and Sonnet use them on short search questions, where the run costs 1.20 to 1.40 times more and answers no better; in Haiku's long sessions they are seldom used, and cost about 6% for their definitions. `alwaysLoad` buys use, not savings.

## Limits

- **Few tasks.** Five search questions and two long sessions, three repetitions each. Sonnet's long sessions are not tested: at about $0.40 to $0.50 a run, the definitions' fixed cost there is about 10% by the same computation.
- **One tool.** The pull comes from sobre's tool descriptions and skill; another server's descriptions might draw more or fewer calls.
- **Failures.** One Haiku search run of `sobre-rc2-mcp` missed one of four facts without calling sobre, and one long-session run of `sobre-rc2-mcp-always` the recap above: neither says anything about the tools.

## Reproduce

```sh
python3 -I fixture/build.py --spec fixture/plants-pilot2.json --out build/pilot2
python3 -I fixture/gen_logs_pilot2.py build/pilot2
bash arms/install.sh sobre-rc2-mcp sobre-rc3-dense
run="--jobs 3 --first-port 5436 --reps 3"
python3 -I harness/bench.py --tasks 'tasks4/ss-*/task.json' \
    --arms native,sobre-rc2-mcp,sobre-rc2-mcp-always,sobre-rc3-dense-always $run --stop-at-usd 1.00 \
    --out results/mcp-always/haiku/raw -- --model claude-haiku-5-5 --fixture build/pilot2/fixture.git
python3 -I harness/bench.py --tasks 'tasks4/ss-*/task.json' --arms native,sobre-rc2-mcp-always $run --stop-at-usd 2.00 \
    --out results/mcp-always/sonnet/raw -- --model claude-sonnet-5-5 --fixture build/pilot2/fixture.git
python3 -I harness/bench.py --tasks 'tasks4/long-*/task.json' --arms native,sobre-rc2-mcp-always $run --stop-at-usd 1.60 \
    --out results/mcp-always/haiku/raw -- --model claude-haiku-5-5 --fixture build/pilot2/fixture.git --timeout-min 45
for model in haiku sonnet; do python3 -I harness/report.py --raw results/mcp-always/$model/raw --out results/mcp-always/$model; done
python3 -I harness/pilot4_summary.py --pilot mcp-always haiku sonnet   # by part, with sobre calls and the cold-start column
```
