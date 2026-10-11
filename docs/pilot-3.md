# Pilot 3: a smaller model, conversations, and sobre's compression levels

Pilots 1 and 2 ran one model, Sonnet 5.5, on one-message tasks, and every run succeeded. Pilot 3 asks three questions they could not answer:

1. **Does a smaller model filter its own output less, leaving more for a context tool to save?** Every task runs on Haiku 5.5 as well as Sonnet 5.5, both at effort `medium`.
2. **What happens when context accumulates over a conversation?** Four new tasks are conversations of four user messages ([pilot-3-tasks.md](pilot-3-tasks.md)).
3. **What does sobre's `compression_level` change?** sobre runs at 0.3 (its default), 0.6 and 0.9.

This pilot measures sobre against Claude Code alone. The other tools are not rerun: their pilot 1 and 2 results stand.

## Setup

- **Tasks:** the 10 tasks of pilot 1 (`tasks/`, pilot 1 fixture), the 6 of pilot 2 (`tasks2/`) and the 4 conversations (`tasks3/`), the last two sets on the pilot 2 fixture.
- **Models:** `claude-sonnet-5-5` and `claude-haiku-5-5`, at effort `medium`, through Claude Code 2.1.296. Limits per run: a $3 cap and 25 minutes, the timeout covering a whole conversation.
- **Arms:**
  - `native`: Claude Code alone;
  - `sobre-dev`: a development build of sobre (sobre-ai `cbab75497`) at `compression_level` 0.3, its default;
  - `sobre-dev-06`: the same build at 0.6;
  - `sobre-dev-09`: the same build at 0.9.
  - `sobre-dev-09b`: build `935756b6b` at 0.9. It replaced `sobre-dev-09` after the first runs showed 0.9 cutting a diff short (below).
- **What the build changes:** sobre's post-run hook now folds output by its shape whatever command printed it, so it also works on the chained lines agents write. Each level adds a rule:
  - at every level, runs of one log statement keep their first and last line;
  - from 0.4, consecutive search results of one file print its path once;
  - from 0.8, long output that cannot hold source keeps its first and last lines.
- **Repetitions:** 2 per task, arm and model.
- **Prices:** `harness/prices.json`. Sonnet 5.5 cache hits cost $0.10 per million tokens. Haiku 5.5 costs $0.10 input and $0.50 output per million tokens, with higher prices for a request whose prompt is over 100K tokens.

## Harness changes for this pilot

- **Parallel runs:** `bench.py --jobs N` runs N at a time, each on its own Postgres server. A server must be UTF8, and `bench.py` checks it.
- **Conversations:** a task's `followups` resume the session with `claude -p --resume`.
- **Isolation:** each turn runs in its own PID namespace, and the prompt goes in on stdin. This came after one agent's `kill` loop reached other runs (PROTOCOL.md changelog).
- **Grading:** a grader kind `all` grades a conversation on the repository's final state and on its last answer together.

## Results

All 448 runs counted are valid; the invalid ones were re-run (see Validity below). On Sonnet every run succeeded. On Haiku every run succeeded except two at 0.6.

### Cost against Claude Code alone

Geometric mean of per-task cost ratios, with 95% bootstrap intervals over tasks. Two repetitions per task; the log conversation on Sonnet has six for `native` and 0.3.

| Arm | Haiku, all 20 tasks | Sonnet, all 20 tasks |
| --- | --- | --- |
| sobre 0.3 (default) | 1.10 (1.02–1.19) | 1.03 (0.98–1.08) |
| sobre 0.6 | 1.05 (0.96–1.17) | 1.00 (0.95–1.05) |
| sobre 0.9, first build (cut diffs) | 1.07 (1.01–1.15) | 0.98 (0.91–1.05) |
| sobre 0.9, fixed build | 1.05 (0.99–1.13) | 0.99 (0.95–1.04) |

By task set (point estimates; intervals in `results/pilot3/<model>/report.md` and the per-set reports):

| Arm | Haiku: pilot 1 tasks | pilot 2 tasks | conversations | Sonnet: pilot 1 tasks | pilot 2 tasks | conversations |
| --- | --- | --- | --- | --- | --- | --- |
| 0.3 | 1.14 | 1.04 | 1.09 | 1.06 | 0.97 | 1.03 |
| 0.6 | 0.99 | 1.01 | 1.30 | 1.01 | 1.01 | 0.94 |
| 0.9, first build | 1.05 | 1.07 | 1.15 | 1.04 | 0.94 | 0.90 |
| 0.9, fixed | 0.99 | 1.12 | 1.14 | 1.03 | 0.95 | 0.97 |

Mean cost per run for `native`: $0.021 on Haiku and $0.25 on Sonnet. A Sonnet conversation costs $0.74 on average, against $0.05 to $0.08 for a one-message task.

### What the hook actually removed

sobre's probe counts the tokens the hook took out of each run. They are far too few to explain the gaps above:

| Arm | Runs where the hook compressed | Tokens removed per run | Worth, as a share of the run's cost |
| --- | --- | --- | --- |
| 0.3, Haiku / Sonnet | 3 of 40 / 5 of 40 | about 300 / 150 | 0.4% / 0.3% |
| 0.6, Haiku / Sonnet | 22 / 19 | about 560 / 300 | 0.7% / 0.6% |
| 0.9, Haiku / Sonnet | 24 / 17 | about 690 / 360 | 0.8% / 0.7% |

No agent read the full output sobre kept, and no agent called a sobre MCP tool.

### One task where sobre helped: the log diagnosis conversation

`mt-reminders-incident` has the agent diagnose a bug from 9.7 MB of scheduler and API logs, fix it, fix a second bug found in the same logs, and write a recap. On Sonnet, every sobre level was cheaper than `native` on average. Of the 36 pairs of a 0.3 run and a `native` run, the sobre run was the cheaper in 28:

| Arm | Runs | Mean cost | Turns | Output tokens |
| --- | --- | --- | --- | --- |
| native | 6 | $0.99 | 24.5 | 32.7k |
| sobre 0.3 | 6 | $0.84 | 22.7 | 27.4k |
| sobre 0.6 | 2 | $0.78 | 21.5 | 25.3k |
| sobre 0.9, first build | 2 | $0.66 | 18.0 | 21.4k |
| sobre 0.9, fixed | 2 | $0.81 | 22.0 | 27.2k |

At 0.3 that is 16% less on average. An exact permutation test on the six against six gives a one-sided p of 0.06: suggestive, not established. The hook removed only 400 to 1,400 tokens per run there, worth under a cent; the saving comes from the runs being shorter, with fewer turns and less reasoning. A plausible mechanism is that a folded log shows its shape (the first and last line of a run of one statement and how many it holds), which shortens the diagnosis. On Haiku the same task showed no such gap.

## What pilot 3 taught

1. **On these tasks sobre costs what Claude Code alone costs, at every level.** On Sonnet, every level lands between 0.98 and 1.03 over the 20 tasks. On Haiku, sobre is 5% to 10% dearer, with the default level's interval above 1. The hook removes under 1% of a run's cost, so these gaps come from what the agent does, not from what sobre compresses.
2. **`compression_level` does not order the results.** 0.6 and 0.9 compress four to six times more often than 0.3, and remove about twice the tokens, but neither is consistently cheaper. The differences between levels are smaller than the noise between repetitions.
3. **A smaller model does not leave more to compress.** Haiku makes about twice as many tool calls as Sonnet, but filters its output the same way (`| head`, `grep -c`, line ranges). The bet that a small model leaves more on the table for a context tool did not hold here.
4. **Conversations amplify everything, including the noise.** A four-message conversation costs about ten times a one-message task. Its cost depends on the path the agent takes in the first messages. Two repetitions are not enough to separate a 10% effect.
5. **Haiku has a cost cliff at 100K tokens of prompt.** Two Haiku runs out of 240 crossed it; one of them, a conversation at 0.6, cost $0.33 against about $0.10 for its neighbours, which alone makes the 0.6 conversation ratio 1.30. A tool that keeps long sessions under the threshold could save a lot on Haiku. None of the arms here tries to.
6. **The 0.9 rule that cut long output short hit a diff once**, and the agent ran the command again. The fixed build keeps diffs, blame, search results and listings whole; it measured the same as the first build within noise.

## Validity

- Every run was billed to its arm's key and is valid. Runs that were not are listed in `meta.json` with the reason and were re-run:
  - runs on two Postgres servers whose `template1` was SQL_ASCII (24 runs: 15 of the main matrix and 9 exploratory `native` runs on Haiku);
  - three runs killed, and one grading killed, by another run's agent before runs were isolated (PROTOCOL.md changelog).
- Before the 9 exploratory runs were re-run, `native` on Haiku showed 4 failures, all on the faulty servers. They made sobre look 10 points more successful on Haiku. That gap disappeared once the runs were re-run.
- **Spend:** $45.27 computed for pilot 3, $63 for the three pilots.
