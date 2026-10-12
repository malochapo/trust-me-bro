# MCP tools the agent does not see

2026-10-12. Across pilots 1 to 4, 454 runs had sobre's MCP server connected and no instruction about it, and no agent called a sobre tool ([pilot 4](pilot-4.md)). That finding has two possible causes: the agent sees the tools and has no use for them, or it does not see them. This page shows the second is real, and adds the arms that tell the two apart.

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

## What they would measure

Against `sobre-rc2-mcp` on pilot 4's part C (search questions worded by behavior) and part A:
- **how often the agent calls a sobre tool unprompted** when the tools are in every request;
- **what the tools cost when visible**: sent with every request, they enlarge the prefix written at each session start and read at every call, which the cold-start cost of [cache-isolation.md](cache-isolation.md) prices without depending on the run order.

A part C run on Haiku cost $0.003 to $0.004 in pilot 4 (`results/pilot4/haiku/raw/ss-*`), so three arms × five tasks × three repetitions would cost well under a dollar, though each `sobre-rc3-dense-always` setup builds its dense index for 8 to 11 minutes. No run has been made yet.
