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
- **Tool results cost more than their size.** A result is written to the cache once, then read again at every later call of the session: Claude Code never drops one in these runs. Counted that way, tool results are about 28% of a native run's cost on one-message tasks and 36% on conversations, on both models (pilot 3, medians), and 43% to 50% on the log conversations. An earlier version of this page said about 5%, which was wrong.
- **What reaches the context is mostly what the agent asked for.** Agents filter their output themselves (`| head`, `grep -c`, `cut -c`, line ranges), and read files with `sed -n` and `cat` far more than with Read. On the log conversations:
  - folding every log statement seen 8 times or more, whatever its numbers, keeping the first and the last occurrence, would remove at most 13% of the outputs' characters without touching a warning or error line; lines repeated word for word but for their timestamp are about 9%. 97% of what such folds remove comes from outputs the agent had already filtered with grep, head, awk or sed;
  - replayed through each build's hook, on the same paths, rc.2 would have removed 0.4% to 6% of a run's cost, folding by statement (malochapo/sobre-ai#106's first commit) 2.4% to 8%, and folding exact repeats only (its second commit) 0.4% to 4%, about 1% on most;
  - no output repeats within a run, and lines already shown earlier in the session make up 6% of the outputs.

Shrinking what the agent asked for therefore saves a few percent at most. A context tool moves cost beyond that only by changing the agent's path: fewer turns, less reasoning. That is what search and memory aim at, and what folded logs seemed to do in pilot 3.

How these figures are computed: `harness/result_share.py` splits each API call's new tokens between the results and messages added since the previous call, and with `--hook` replays each native result through a build's hook.

## Tasks (`tasks4/`, pilot 2 fixture)

| Part | Task | What it is |
| --- | --- | --- |
| A, long sessions | `long-incident-then-dedup` | Three messages of `mt-reminders-incident`, `/compact`, three of `mt-dedup-snooze-regressions`, then one recap that needs facts from both halves |
| A | `long-security-then-redaction` | The same with `mt-security-review` and `mt-redaction-entities` |
| B, the next day | `xs-reminders-next-day` | Day 1 diagnoses the reminder bug from the logs. Day 2, a new session, fixes it and gives day 1's facts (file, function, commit, image tag, first missed Monday) |
| B2, the next day after saving | `xs-reminders-saved`, `xs-dedup-saved` | The part B tasks with one more message at the end of day 1: the user asks the agent to save what was found for tomorrow. Both arms then save on purpose, and day 2 measures how well each mechanism brings it back |
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
| `sobre-rc3-dense` | sobre 0.1.0-rc.3, the build with local embeddings: `--mcp`, model provisioned, index prebuilt. From rc.3, semantic search ranks by hybrid by default | C |
| `sobre-rc3-dense-told` | `sobre-rc3-dense` with the CLAUDE.md of `sobre-rc2-mcp-told` | C |
| `sobre-dev-fold2` | A build of malochapo/sobre-ai#106's first commit, set up as `sobre-rc2`: log lines of one statement fold whatever their numbers, warnings and errors never | D |
| `sobre-dev-fold3` | A build of #106's second commit, set up as `sobre-rc2`: only log lines repeated but for their timestamp fold | D |

The `-told` arms do not compare sobre with Claude Code. They measure what the tools are worth once an agent uses them, which in pilots 1 to 3 never happened. If they win, the next question is how an agent finds the tools on its own.

## Plan and budget

Haiku 5.5 and Sonnet 5.5 at effort `medium`, with the run limits of pilot 3.

| Part | Arms | Repetitions | Runs per model | Estimate (Sonnet + Haiku) |
| --- | --- | --- | --- | --- |
| A | native, sobre-rc2, sobre-rc2-mcp | 3 | 18 | $9 + $1 |
| B | native, native-told, sobre-rc2-mcp, sobre-rc2-mcp-told | 3 | 24 | $5 + $1 |
| C | native, sobre-rc2-mcp, sobre-rc2-mcp-told, then sobre-rc3-dense and sobre-rc3-dense-told | 3 | 75 | $6 + $1 |
| B2 | the four arms of B | 3 | 24 | $5 + $0.5 |
| D | native, sobre-rc2, then sobre-dev-fold2 and sobre-dev-fold3 | 6 (new task), 4 (pilot 3's) | 20, then 40 | $6 + $0.5, then $6 + $1 |

That is about $28, with the rest of the month's $55 kept for re-runs. Estimates use pilot 3's corrected costs.

## What the smoke runs found

One run per new arm on Haiku (`results/pilot4/smoke/`), before the pilot:

- **Long sessions:** the 8-message conversation and its `/compact` work. The compaction took the context from 73,880 tokens to 6,072, and the recap still had every fact from before it. It took 11 minutes on Haiku, so part A runs with a 45-minute limit.
- **Next-day sessions:** two sessions per run, as intended. Claude Code alone wrote nothing to its memory between them.
- **The -told arms:** the agent loads sobre's tools through tool search and calls `sobre_session` and `sobre_search` as asked.
- **Two defects of sobre rc.2's dense search:**
  - `sobre_search action=semantic` uses BM25 unless the agent passes `mode`, even in the build with embeddings and with the model installed. So the dense build without a told CLAUDE.md is the BM25 arm, and is not run.
  - In one session, a first hybrid search used the embeddings (coverage 100%), and the next one answered "dense index not built" and fell back to BM25.

  Both are fixed in sobre 0.1.0-rc.3 (malochapo/sobre-ai#103), which the dense arms run.
- **Provisioning in a clean environment:** sobre's model download needs the network proxy, which the harness's clean environment does not pass. The model and ONNX Runtime are provisioned once with network access, into `$BENCH_TOOLS/cache/sobre-dense-home`, and linked into each run. sobre's message for a failed download blamed the model ("must ship onnx/model.onnx"), not the network.

## Results

The pilot cost $36.06 (Haiku $4.80, Sonnet $31.11, smoke runs $0.15). Ratios are geometric means of per-task cost ratios to `native`, with 95% bootstrap intervals over tasks (`harness/pilot4_summary.py`). With two tasks per part, an interval says little: the run-level figures carry the findings.

### No agent calls sobre's tools on its own

Across pilots 1 to 4, 454 runs had sobre's MCP server connected and no CLAUDE.md about it: the agent called a sobre tool 0 times. Claude Code loads MCP tools through tool search, and an agent that greps and edits well has no reason to look for them. Only the `-told` arms used them.

### Memory (parts B and B2): Claude Code's own memory does the job, sobre's does it worse

What was saved on day 1 and what day 2 cost:

| Part | Arm | Haiku: saved in | Haiku: day 2 | Sonnet: saved in | Sonnet: day 2 |
| --- | --- | --- | --- | --- | --- |
| B | `native` | nothing | $0.025 | nothing | $0.122 |
| B | `native-told` | Claude Code's memory, 6/6 | $0.016 | Claude Code's memory, 2/6 | $0.146 |
| B | `sobre-rc2-mcp` | nothing | $0.015 | nothing | $0.141 |
| B | `sobre-rc2-mcp-told` | sobre, 2/6 | $0.015 | nothing | $0.141 |
| B2 | `native` | Claude Code's memory, 6/6 | $0.016 | Claude Code's memory, 6/6 | $0.103 |
| B2 | `native-told` | Claude Code's memory, 6/6 | $0.016 | Claude Code's memory, 6/6 | $0.067 |
| B2 | `sobre-rc2-mcp` | Claude Code's memory, 6/6 | $0.015 | Claude Code's memory, 6/6 | $0.068 |
| B2 | `sobre-rc2-mcp-told` | sobre, and Claude Code's memory in 4/6 | $0.013 | sobre, 6/6 | $0.147 |

- **Asked to save for tomorrow, every agent uses Claude Code's memory**, with sobre's server connected too, and the next session loads it by itself.
- **sobre's memory needs a CLAUDE.md and two explicit calls.** Told to use it, Sonnet saved to sobre in 6 runs of 6, then loaded it the next day in 3: its day 2 cost $0.147, against $0.067 to $0.103 with Claude Code's memory and $0.122 with nothing saved. B2's told arm costs 1.23 times native on Sonnet (1.14–1.34).
- **Without the request (part B), little is saved at all.** Told to keep what a later session needs, Haiku wrote Claude Code's memory in every `native-told` run, and sobre's in 2 of 6 `sobre-rc2-mcp-told` runs. Sonnet wrote Claude Code's memory in 2 of 6, and sobre's in none.
- **Every arm found day 1's facts on day 2** (all runs pass but one Haiku B2 run of `sobre-rc2-mcp`).

### Search (part C)

| Arm | Haiku | Sonnet |
| --- | --- | --- |
| `sobre-rc2-mcp` | 1.07 (0.99–1.19) | 1.04 (0.99–1.09) |
| `sobre-rc2-mcp-told` | 1.27 (1.22–1.36) | 1.05 (0.97–1.11) |
| `sobre-rc3-dense-told` | 1.31 (1.21–1.40) | 1.08 (0.97–1.26), one repetition |

- All runs of all arms pass: the five questions are answered by grep and reading as well as by search.
- **Local embeddings change nothing here.** rc.3's semantic search ranked by hybrid with the embeddings (coverage 100%), as its fixes intended, and the told agent used it as often as BM25 (13 semantic searches in 15 Haiku runs, against 12), at the same cost. A dense setup builds the index in 8 to 11 minutes per run, so the untold dense arm, which would only have repeated the 0 calls above, was stopped after 2 Haiku runs, and the told one ran once per task on Sonnet.
- Told to search by meaning, Haiku loaded the tools through tool search, loaded its session, searched, then grepped and read as native does: 8.5 turns against 5.7. Sonnet, told the same, called no sobre tool in 20 runs, with the BM25 build or the dense one.

### Long sessions (part A)

| Arm | Haiku | Sonnet |
| --- | --- | --- |
| `sobre-rc2` | 1.01 (1.01–1.02) | 0.91 (0.86–0.98) |
| `sobre-rc2-mcp` | 1.03 (1.00–1.07) | 0.98 (0.97–0.98) |

The recap after `/compact` had every fact from before it in all runs but two on Haiku, one native and one `sobre-rc2-mcp`, each missing one fact. The hooks only on Sonnet are the one gap here, on two tasks with three repetitions each: too few runs to tell 9% from noise.

### Logs (part D)

| Arm | Haiku | Sonnet |
| --- | --- | --- |
| `sobre-rc2` | 1.00 (0.82–1.21), 10/10 pass | 0.90 (0.81–1.00), 10/10 |
| `sobre-dev-fold2` | 0.67 (0.55–0.82), 12/14 pass | 4 runs of one task, 4/4 |
| `sobre-dev-fold3` | 0.85 (0.80–0.91), 10/10 pass | 1.10 (0.98–1.23), 10/10 |

- **Folding by statement hid values.** In two `sobre-dev-fold2` Haiku runs, the agent listed the case cost sync's diff lines to find the first inflated case (`awk … | grep 'costsync.diff|done in' | head -40`). The fold kept the first and last of 26 lines and folded the 24 between them, and both times the agent named the wrong date. Native named the right one in all 10 runs. The cheapest `sobre-dev-fold2` run was one of the two that failed. 97% of what that fold removes in replay comes from outputs the agent had filtered with grep, head, awk or sed.
- **Haiku's native runs drifted.** Native's first six runs of `mt-logs-case-cost` cost $0.054 on average; four more, run alongside `sobre-dev-fold2` hours later, cost $0.042. Over those four pairs, `sobre-dev-fold2` cost 0.91 of native. `sobre-dev-fold3` ran later still, with no native run beside it, so its Haiku ratio mixes the fold and the drift.
- **What the fold removes, on the same paths** (1,106 Bash outputs of native log-task runs replayed through each hook):

  | Build | Outputs compressed | Chars removed | WARN/ERROR-type lines hidden | Values hidden |
  | --- | --- | --- | --- | --- |
  | rc.2 | 111 | 7.4% | 76 | yes |
  | `sobre-dev-fold2` | 116 | 11.7% | 0 | yes |
  | `sobre-dev-fold3` | 48 | 3.2% | 0 | no |

So folding logs cannot save much on these tasks without hiding what the agent asked for: the fold that hides nothing removes 0.4% to 4% of a log conversation's cost, about 1% on most. Its value is not hiding the warnings and values rc.2 hides.
