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
| native | $0.055 | 1 | | 5.2 | 92.7k | 11.8k |
| rtk | $0.059 | 1.06 | 1.01–1.11 | 5.8 | 103.5k | 12.6k |
| sobre | $0.062 | 1.13 | 1.04–1.24 | 6.3 | 108.4k | 13.2k |
| Headroom | $0.062 | 1.14 | 1.06–1.25 | 5.6 | 92.2k | 14.5k |
| lean-ctx | $0.089 | 1.62 | 1.43–1.82 | 8.9 | 140.9k | 21.3k |

On these tasks, every tool costs more than Claude Code alone, and each 95% interval lies above 1. The runs are short: 5 to 9 turns, about 30 seconds, and tool outputs of a few thousand characters. So there is little to compress, and what decides the cost is each tool's fixed overhead: the tool definitions and instructions it adds to the prompt prefix, which is written to the cache once and re-read on every turn, and the extra turns its tools invite.

**Correction (2026-10-12).** Part of that overhead was the shared prompt cache. native, rtk and sobre start from one prompt prefix, which each of their runs found warm; Headroom and lean-ctx have prefixes of their own, found warm at 16 and 14 of their 20 starts. With every session priced as if it had started cold, the ratios are rtk 1.04 (1.00–1.08), sobre 1.08 (1.02–1.16), Headroom 1.00 (0.97–1.03) and lean-ctx 1.40 (1.31–1.49): Headroom costs what native costs ([cache-isolation.md](cache-isolation.md)).

**Spend:** $6.56 for the 100 runs, computed from tokens and public prices. That matches Claude Code's own estimate to the cent. A first version of this report overstated it at $7.63: it priced Sonnet 5.5 cache hits at $0.20 per million tokens instead of $0.10 (0.05× base input; PROTOCOL.md changelog). Add about $0.17 for the judge and $0.29 for the leakage check.

| Arm | Computed spend |
| --- | --- |
| native | $1.10 |
| rtk | $1.17 |
| Headroom | $1.25 |
| sobre | $1.25 |
| lean-ctx | $1.79 |

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
7. **What made sobre dearer, and a fix.** A development build of sobre was measured on the same tasks after the pilot. It costs what native costs (1.02, 95% CI 0.97–1.07). An A/A arm showed the noise of this design: about ±5% on 10 tasks × 2 repetitions. See [sobre-dev.md](sobre-dev.md). Phase 2 should include such an arm.
