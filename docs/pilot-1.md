# Pilot 1: results

Run on 2026-10-10, under [PROTOCOL.md](../PROTOCOL.md) as of that day. The aggregate numbers are in [results/report.md](../results/report.md), and every run's raw data is in `results/raw/`.

## Setup

- **Model:** Claude Code 2.1.296 with `claude-sonnet-5-5` at effort `medium`.
- **Fixture:** Dispatch with 8 planted commits.
- **Runs:** 10 tasks × 5 arms × 2 repetitions = 100 runs.
- **Authentication and limits:** one API key per arm and a $3 cap per run.

The arms ran at their pinned versions: sobre 0.1.0-rc.1, lean-ctx 3.11.2, Headroom 0.40.0 (`[sandbox]`, proxy mode) and rtk 0.51.0.

## Results

All 100 runs were valid: each was billed to its arm's key, and the MCP servers of its arm connected. All 100 succeeded.

| Arm | Mean cost per run | Cost vs native, geometric mean of per-task ratios | 95% CI | Turns | Cache read | Cache write |
| --- | --- | --- | --- | --- | --- | --- |
| native | $0.065 | 1 | | 5.2 | 92.7k | 11.8k |
| rtk | $0.069 | 1.06 | 1.01–1.12 | 5.8 | 103.5k | 12.6k |
| Headroom | $0.072 | 1.12 | 1.05–1.21 | 5.6 | 92.2k | 14.5k |
| sobre | $0.073 | 1.13 | 1.03–1.25 | 6.3 | 108.4k | 13.2k |
| lean-ctx | $0.103 | 1.59 | 1.42–1.79 | 8.9 | 140.9k | 21.3k |

On these tasks, every tool costs more than Claude Code alone, and each 95% interval lies above 1. The runs are short: 5 to 9 turns, about 30 seconds, and tool outputs of a few thousand characters. So there is little to compress, and what decides the cost is each tool's fixed overhead: the tool definitions and instructions it adds to the prompt prefix, which is re-read on every turn, and the extra turns its tools invite.

**Spend:** $7.63 for the 100 runs, computed from tokens and public prices. Claude Code's own estimate is about 15% lower. Our formula prices cache writes at 1.25× input, the published rate, and checking the Console bill per key will settle which number is right. Add about $0.17 for the judge and $0.29 for the leakage check.

| Arm | Computed spend | Claude Code's estimate |
| --- | --- | --- |
| native | $1.29 | $1.10 |
| rtk | $1.38 | $1.18 |
| Headroom | $1.43 | $1.25 |
| sobre | $1.46 | $1.25 |
| lean-ctx | $2.07 | $1.79 |

## What the pilot taught

1. **The tasks are too easy to separate the arms on success.** Sonnet 5.5 solved all of them. The pilot measured cost only, and only on short sessions, which favours the native arm by construction. Hence [pilot 2](pilot-2.md): longer tasks, with much more context to read and repeat.
2. **Three grader defects were found and fixed.** All three rejected correct answers; the details are in PROTOCOL.md's changelog. Every fact-graded run was re-graded with the final rules, the same for every arm. Fact graders now match answer lines from the start of the line, and accept any correct spelling of a path.
3. **Phase 0 caught one task answered from memory.** `qa-ui-entity-stats` was rewritten and checked again.
4. **The harness held up:**
   - no invalid run;
   - the billing check confirmed every run's key;
   - an interrupted run (the container was restarted) was re-run cleanly.
5. **Flags:**
   - One rtk run ran `pip install` twice while trying to get tests to run. It did not reach the upstream code.
   - One rtk run's hook made no rewrite, so its probe saw no activity.
6. **Cost per task varies a lot from one repetition to the next.** For example, sobre on `fix-signal-stats-scope` cost $0.177 in repetition 1 and $0.08 in repetition 2. Two repetitions are a minimum; phase 2 should run at least three.
