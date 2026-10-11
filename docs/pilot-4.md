# Pilot 4: long sessions, memory, search, and the log effect

Pilot 3 measured sobre's post-run hook at three compression levels and found it costs what Claude Code alone costs. It also found where the money goes, and that only the agent's path can move it ([pilot-3.md](pilot-3.md)). Pilot 4 tests the parts of sobre pilot 3 never reached:

- **Long sessions.** Context piles up, and Claude Code compacts the conversation.
- **Memory across sessions.** Work resumes the next day in a new session.
- **Semantic search, with and without local embeddings.**
- **Whether the log effect replicates.** In pilot 3, one log diagnosis conversation was 12% cheaper with sobre (p = 0.09).

It runs sobre 0.1.0-rc.2 as released. From rc.2, `sobre init` connects the hooks only, and the MCP server and the skill are opt-in (`--mcp`).

## Where a run's money goes

Native runs of pilot 3 (Sonnet):

| Share of cost | One-message tasks | Conversations |
| --- | --- | --- |
| Cache writes | 52% | 41% |
| Output (with reasoning) | 30% | 34% |
| Cache reads | 17% | 25% |

- **Most cache writes are the context, written once:** Claude Code's system prompt and tools at the first call, then each new message and tool result.
- **Tool results are small.** Agents filter their output themselves (`| head`, `grep -c`, line ranges), and read files with `sed -n` and `cat` far more than with Read. Removing every tool result outright would save about 5% of a Sonnet conversation.
- **No tool output repeated** within a run, so deduplicating outputs has nothing to find on these tasks.

A context tool can therefore move cost mainly by changing the agent's path: fewer turns, less reasoning. That is what search and memory aim at, and what folded logs seem to do.

## Tasks (`tasks4/`, pilot 2 fixture)

| Part | Task | What it is |
| --- | --- | --- |
| A, long sessions | `long-incident-then-dedup` | Three messages of `mt-reminders-incident`, `/compact`, three of `mt-dedup-snooze-regressions`, then one recap that needs facts from both halves |
| A | `long-security-then-redaction` | The same with `mt-security-review` and `mt-redaction-entities` |
| B, the next day | `xs-reminders-next-day` | Day 1 diagnoses the reminder bug from the logs. Day 2, a new session, fixes it and gives day 1's facts (file, function, commit, image tag, first missed Monday) |
| B | `xs-dedup-next-day` | Day 1 lists the snooze and deduplication commits. Day 2, a new session, finds which one broke deduplication windows, fixes it, and gives day 1's facts |
| C, search | `ss-signal-post-redraw`, `ss-latecomer-briefing`, `ss-call-invite-choice`, `ss-thread-case-bring-in`, `ss-oncall-turn-tally` | Questions worded by behaviour, not by the code's words, each needing a file, a function and a fact from reading the code |
| D, logs | `mt-logs-case-cost` | A new log diagnosis conversation: a case cost bug (`q2-case-cost-cutoff`), 6.9 MB of three logs in other formats than pilot 2's |
| D | `mt-reminders-incident` (`tasks3/`) | Pilot 3's log conversation, with more repetitions |

### How the new tasks run

- **Part A:** `/compact` is sent as a message. Claude Code compacts the session as it would on a long session, and the next message resumes from the summary.
- **Part B:** the day 2 message is `{"prompt": ..., "new_session": true}`. It starts a new session in the same repository and home: Claude Code's own memory and sobre's data persist, the conversation does not.
- **Part C:** the six questions were checked for leakage (Sonnet 5.5, no code, three repetitions). Four were answered from memory and replaced or dropped; the five kept were 0/3 (`results/pilot4/leakage/`).
- **All tasks:** every task passes `tasks/validate.py`.

## Arms

| Arm | What it is | Parts |
| --- | --- | --- |
| `native` | Claude Code alone | all |
| `native-told` | Claude Code alone, with a user CLAUDE.md asking it to keep what a later session needs in its memory | B |
| `sobre-rc2` | sobre rc.2 as `sobre init claude` sets it up: the hooks only | A, D |
| `sobre-rc2-mcp` | rc.2 with `--mcp`: hooks, MCP server, skill, and a prebuilt index | A, B, C |
| `sobre-rc2-mcp-told` | `sobre-rc2-mcp`, with a user CLAUDE.md that says when to use `sobre_search` (semantic) and `sobre_session` | B |
| `sobre-rc2-dense-told` | the rc.2 build with local embeddings, `--mcp`, model provisioned, index prebuilt, and a CLAUDE.md that also asks for `mode="hybrid"` | C, after the fixes below |

The `-told` arms do not compare sobre with Claude Code. They measure what the tools are worth once an agent uses them, which in pilots 1 to 3 never happened. If they win, the next question is how an agent finds the tools on its own.

## Plan and budget

Haiku 5.5 and Sonnet 5.5 at effort `medium`, with the run limits of pilot 3.

| Part | Arms | Repetitions | Runs per model | Estimate (Sonnet + Haiku) |
| --- | --- | --- | --- | --- |
| A | native, sobre-rc2, sobre-rc2-mcp | 3 | 18 | $9 + $1 |
| B | native, native-told, sobre-rc2-mcp, sobre-rc2-mcp-told | 3 | 24 | $5 + $1 |
| C | native, sobre-rc2-mcp, sobre-rc2-mcp-told (then the dense arm) | 3 | 45 (+15) | $4 + $1 |
| D | native, sobre-rc2 | 6 (new task), 4 (pilot 3's) | 20 | $6 + $0.5 |

That is about $28, with the rest of the month's $55 kept for re-runs. Estimates use pilot 3's corrected costs.

## What the smoke runs found

One run per new arm on Haiku (`results/pilot4/smoke/`), before the pilot:

- **Long sessions:** the 8-message conversation and its `/compact` work. The compaction took the context from 73,880 tokens to 6,072, and the recap still had every fact from before it. It took 11 minutes on Haiku, so part A runs with a 45-minute limit.
- **Next-day sessions:** two sessions per run, as intended. Claude Code alone wrote nothing to its memory between them.
- **The -told arms:** the agent loads sobre's tools through tool search and calls `sobre_session` and `sobre_search` as asked.
- **Two defects of sobre rc.2's dense search:**
  - `sobre_search action=semantic` uses BM25 unless the agent passes `mode`, even in the build with embeddings and with the model installed. So the dense build without a told CLAUDE.md is the BM25 arm, and is not run.
  - In one session, a first hybrid search used the embeddings (coverage 100%), and the next one answered "dense index not built" and fell back to BM25.

  The dense arm waits for both to be fixed.
- **Provisioning in a clean environment:** sobre's model download needs the network proxy, which the harness's clean environment does not pass. The model and ONNX Runtime are provisioned once with network access, into `$BENCH_TOOLS/cache/sobre-dense-home`, and linked into each run. sobre's message for a failed download blamed the model ("must ship onnx/model.onnx"), not the network.
