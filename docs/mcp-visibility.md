# MCP tools the agent does not see

2026-10-12. Across pilots 1 to 4, 454 runs had sobre's MCP server connected and no instruction about it, and no agent called a sobre tool ([pilot 4](pilot-4.md)). That finding has two possible causes: the agent sees the tools and has no use for them, or it does not see them. This page shows the second is real, adds the arms that tell the two apart, and runs them: loaded up front, the tools are used in every run, and the run costs more for the same answers.

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

## The test

2026-10-13, on pilot 4's part C (five search questions worded by behaviour, not by the code's words), with Haiku 5.5 at effort `medium` and pilot 4's settings and fixture (`build/pilot2`, HEAD `51546e1`). Four arms, three repetitions, interleaved, three runs at a time:
- `native`;
- `sobre-rc2-mcp`, the tools deferred, as in pilots 1 to 4;
- `sobre-rc2-mcp-always` and `sobre-rc3-dense-always`, the tools loaded up front.

60 runs, all valid and billed to their arm's key, for $0.24, plus $0.01 for one smoke run per new arm (`results/mcp-always/smoke/`). The paired report is [results/mcp-always/haiku/report.md](../results/mcp-always/haiku/report.md).

## Results

| Arm | Runs that called sobre | sobre calls per run | Success | Turns | Cost vs native | Cold start |
| --- | --- | --- | --- | --- | --- | --- |
| `native` | 0/15 | 0 | 15/15 | 5.8 | 1 | 1 |
| `sobre-rc2-mcp`, deferred | 0/15 | 0 | 14/15 | 5.4 | 0.98 (0.88–1.11) | 0.98 (0.91–1.07) |
| `sobre-rc2-mcp-always` | 15/15 | 3.3 | 15/15 | 6.3 | 1.43 (1.17–1.67) | 1.32 (1.22–1.41) |
| `sobre-rc3-dense-always` | 15/15 | 3.9 | 15/15 | 6.2 | 1.24 (1.00–1.53) | 1.20 (1.09–1.32) |

Cost: geometric mean of per-task cost ratios, 95% bootstrap interval over the five tasks.

1. **The agents had not seen the tools.** Deferred, no run called sobre, as in the 454 runs before. Loaded up front, every run did, with no instruction about them, and every run began with them: `sobre_compose` once, then sobre's regex search and its file reader where native uses grep and `sed` in a shell. Shell calls per run fell from 4.7 to 1.7 (rc.2) and 0.4 (rc.3).
2. **Seen, they cost more for the same answers.** Every run of both arms succeeded, and a run cost 1.20 to 1.32 times native's with a cold cache. Most of that is the tools themselves: their definitions add about 6,900 tokens to every request (24,256 tokens in the first request, against 17,345), written once and read at every call. Priced that way, they make $0.0012 of rc.2's $0.0015 extra per run and all of rc.3's; the rest of the run costs what native's does, within 7%.
3. **No agent searched by meaning.** The questions are worded so that the code's words do not match them, which is what sobre's semantic search is for. It was never called: every search was by regular expression (and one by symbol). The visible tools replaced grep; they did not change how the agent looks for code.
4. **rc.2 against rc.3.** The dense build's arm cost less, but the intervals overlap and its agents did not use what the dense build adds.

So the finding becomes narrower and firmer: agents do not use an MCP server's tools that Claude Code defers; loaded up front, they use them in every run, and on these questions the run costs more and answers no better. `alwaysLoad` buys use, not savings.

## Limits

- **One model, short runs.** Haiku only, five or six turns per run, 15 runs per arm. Sonnet, which in pilot 4 called no sobre tool even when told to, is not tested.
- **One tool.** The pull comes from sobre's tool descriptions and skill; another server's descriptions might draw more or fewer calls.
- **Search questions only.** Long sessions (part A), where a tool's fixed cost weighs less and a wrong path more, are not run.
- **One failure,** in `sobre-rc2-mcp`: one run missed one of four facts and called no sobre tool, so it says nothing about the tools.

## Reproduce

```sh
python3 -I fixture/build.py --spec fixture/plants-pilot2.json --out build/pilot2
bash arms/install.sh sobre-rc2-mcp sobre-rc3-dense
python3 -I harness/bench.py --tasks 'tasks4/ss-*/task.json' \
    --arms native,sobre-rc2-mcp,sobre-rc2-mcp-always,sobre-rc3-dense-always --reps 3 \
    --jobs 3 --first-port 5436 --stop-at-usd 1.00 --out results/mcp-always/haiku/raw \
    -- --model claude-haiku-5-5 --fixture build/pilot2/fixture.git
python3 -I harness/report.py --raw results/mcp-always/haiku/raw --out results/mcp-always/haiku
python3 -I harness/pilot4_summary.py --pilot mcp-always haiku   # sobre calls and the cold-start column
```
