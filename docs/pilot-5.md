# Pilot 5: the released tools on long conversations

Run on 2026-10-12. Pilots 1 and 2 measured rtk, Headroom and lean-ctx on single-message tasks, with Sonnet only. Those runs were short (5 to 11 turns), so there was little context for a tool to compress. Pilot 5 measures the same three tools on pilot 4's long conversations, with Haiku and Sonnet.

## Setup

- **Agent:** Claude Code 2.1.296, with `claude-haiku-5-5` and `claude-sonnet-5-5` at effort `medium`. Limits per run: a $3 cap and 25 minutes, or 45 minutes for part A.
- **Tasks:** pilot 4's parts A and D ([pilot-4.md](pilot-4.md)).
  - Part A: two long sessions compacted with `/compact` (`long-incident-then-dedup`, `long-security-then-redaction`).
  - Part D: two log-diagnosis conversations (`mt-logs-case-cost`, `mt-reminders-incident`).
  - Haiku ran all four. Sonnet ran one task of each part (`long-security-then-redaction`, `mt-logs-case-cost`), to fit the budget.
- **Arms:** `native`, then each tool at the version pinned on 2026-10-10:
  - rtk 0.51.0;
  - Headroom 0.40.0;
  - lean-ctx 3.11.2. lean-ctx 3.11.4 came out on 2026-10-11, but its release could not be downloaded from the run machine.
  
  Whether rtk has a newer release could not be checked from that machine either.
- **Runs:** 3 repetitions, the arms interleaved in a seeded order, 3 runs at a time.
- **Totals:** 72 runs, all valid. Spend $13.52: Haiku $3.53, Sonnet $9.99.

**Interruptions.** The run machine was suspended or restarted four times during the pilot. The runs in flight were not recorded as finished, and `bench.py` ran them again. Every recorded run ran without interruption.

## Results

Cost relative to native: the geometric mean of per-task ratios of mean cost. The 95% interval comes from a bootstrap over runs within each task (4,000 resamples). With two to four tasks, a bootstrap over tasks, as in pilots 1 and 2, would say nothing.

**Haiku 5.5**, 4 tasks, 12 runs per arm:

| Arm | Success | Mean cost | Cost vs native (95% CI) | Turns | Cache reads per run |
| --- | --- | --- | --- | --- | --- |
| native | 11/12 | $0.061 | 1 | 51.8 | 2.44M |
| Headroom | 12/12 | $0.050 | 0.89 (0.81–1.01) | 50.9 | 2.08M |
| rtk | 9/12 | $0.083 | 1.48 (1.21–1.75) | 73.9 | 3.68M |
| lean-ctx | 12/12 | $0.100 | 1.78 (1.28–2.25) | 73.6 | 3.36M |

**Sonnet 5.5**, 2 tasks, 6 runs per arm:

| Arm | Success | Mean cost | Cost vs native (95% CI) | Turns | Cache reads per run |
| --- | --- | --- | --- | --- | --- |
| native | 6/6 | $0.364 | 1 | 30.0 | 0.97M |
| Headroom | 6/6 | $0.403 | 1.11 (0.98–1.22) | 32.5 | 1.06M |
| rtk | 6/6 | $0.437 | 1.19 (1.05–1.35) | 37.8 | 1.28M |
| lean-ctx | 6/6 | $0.460 | 1.23 (1.16–1.31) | 39.2 | 1.28M |

Per-task tables are in `results/pilot5/{haiku,sonnet}/report.md`. They can also be printed with `python3 -I harness/pilot4_summary.py --pilot pilot5`. Every tool's probe reported it active in every run.

**Correction (2026-10-12).** Headroom and lean-ctx have prompt prefixes of their own, which only their own runs warmed: they started warm at 1 and 3 of their 12 Haiku sessions, native and rtk at all of them. With every session priced as if it had started cold, the ratios move little on conversations this long: on Haiku, Headroom 0.87 (0.79–0.98), rtk 1.47 (1.20–1.74), lean-ctx 1.74 (1.26–2.20); on Sonnet, Headroom 1.07 (0.97–1.16), rtk 1.18 (1.05–1.33), lean-ctx 1.18 (1.12–1.25) ([cache-isolation.md](cache-isolation.md)).

## What pilot 5 found

1. **Headroom is the only tool measured below native, and only on Haiku.**
   - On Haiku: 0.89 (0.81–1.01). Its proxy compresses tool results inside each request, and Haiku's runs read 15% fewer tokens from the cache.
   - The interval touches 1, and the tasks disagree: 0.62 and 0.82 on two of them, 1.11 and 1.13 on the other two.
   - On Sonnet, Headroom costs more: 1.11 (0.98–1.22).
2. **lean-ctx and rtk cost more on both models.**
   - lean-ctx: 1.78 on Haiku, 1.23 on Sonnet. rtk: 1.48 on Haiku, 1.19 on Sonnet.
   - Both add turns: about 74 against 52 on Haiku, 38 to 39 against 30 on Sonnet.
   - The longer conversations did not turn their compression into a saving.
3. **Haiku with rtk went looking for its environment.**
   - In all 12 Haiku runs with rtk, the agent tried to reinstall the project's dependencies with `pip install`. No run of any other arm did, so all 12 were flagged for network access.
   - Those runs made the most turns, and 3 of the 12 failed, against 1 of 12 for native.
   - rtk's directory listings mark entries as filtered or hidden (`(1 filtered)`, `[+1 hidden: rtk recall …]`). Whether that is what sent the agent to check its setup was not established.
   - On Sonnet, 1 rtk run of 6 did the same.
4. **Success is otherwise unchanged.** All 24 Sonnet runs succeeded. On Haiku, native, Headroom and lean-ctx failed at most once.

## Limits

- **Few tasks.** There are four tasks on Haiku and two on Sonnet. The intervals carry the noise between runs, not between tasks.
- **Still short next to real sessions.** In these conversations the median prompt is 26,000 to 69,000 tokens. Real long sessions run to several hundred thousand ([clearing.md](clearing.md)).
- **Headroom estimates token counts.** As in pilots 1 and 2, its tiktoken vocabularies could not be downloaded on the run machine ([arms/README.md](../arms/README.md)).

## Run

Per model, with `cap` at 5 for Haiku and 12 for Sonnet. Sonnet's part A ran `long-security-then-redaction` only, and it skipped `mt-reminders-incident`.

```sh
common="--arms native,lean-ctx,headroom,rtk --reps 3 --jobs 3 --first-port 5436 --out results/pilot5/$model/raw --stop-at-usd $cap"
run="-- --model claude-$model-5-5 --fixture build/pilot2/fixture.git"
python3 -I harness/bench.py --tasks 'tasks4/long-*/task.json' $common $run --timeout-min 45
python3 -I harness/bench.py --tasks 'tasks4/mt-logs-case-cost/task.json' $common $run
python3 -I harness/bench.py --tasks 'tasks3/mt-reminders-incident/task.json' $common $run
python3 -I harness/report.py --raw results/pilot5/$model/raw --out results/pilot5/$model
```
