# sobre-bench report

50 scored runs (graded, or timed out or errored, which count as failures) out of 50. Bootstrap: 10000 resamples over tasks, seed 20261010. Non-inferiority margin: 5.0 percentage points of success. Cost: tokens x harness/prices.json (client estimate alongside).

## Per arm

| arm | runs | success | cost mean $ | cost median $ | client cost $ | input | output | cache read | cache write 5m | cache write 1h | turns | wall s | tool calls |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| native | 10 | 100.0% | 0.0663 | 0.0700 | 0.0565 | 11 | 1,650 | 98,731 | 12,024 | 0 | 5.5 | 26 | 4.5 |
| sobre | 10 | 100.0% | 0.0767 | 0.0658 | 0.0646 | 12 | 1,943 | 120,540 | 13,235 | 0 | 6.5 | 37 | 5.5 |
| lean-ctx | 10 | 100.0% | 0.1084 | 0.1235 | 0.0956 | 11 | 2,177 | 128,520 | 24,364 | 0 | 8.8 | 25 | 7.8 |
| headroom | 10 | 100.0% | 0.0770 | 0.0762 | 0.0679 | 10 | 1,681 | 90,753 | 16,797 | 0 | 5.5 | 29 | 4.5 |
| rtk | 10 | 100.0% | 0.0679 | 0.0665 | 0.0572 | 11 | 1,780 | 106,439 | 11,509 | 0 | 6.0 | 36 | 5.0 |

## Paired with native (per-task means over reps)

| arm | tasks | Δ success (pp) | 95% CI | cost ratio (geo mean) | 95% CI | success verdict |
|---|---|---|---|---|---|---|
| sobre | 10 | 0.0 | [0.0, 0.0] | 1.123 | [0.948, 1.359] | non-inferior |
| lean-ctx | 10 | 0.0 | [0.0, 0.0] | 1.663 | [1.422, 2.002] | non-inferior |
| headroom | 10 | 0.0 | [0.0, 0.0] | 1.177 | [1.025, 1.378] | non-inferior |
| rtk | 10 | 0.0 | [0.0, 0.0] | 1.024 | [0.935, 1.123] | non-inferior |

## Per task (success rate / mean cost $)

| task | native | sobre | lean-ctx | headroom | rtk |
|---|---|---|---|---|---|
| change-filter-reason | 100% / 0.097 | 100% / 0.112 | 100% / 0.148 | 100% / 0.118 | 100% / 0.110 |
| fix-signal-stats-scope | 100% / 0.077 | 100% / 0.177 | 100% / 0.122 | 100% / 0.121 | 100% / 0.106 |
| fix-snooze-expired-filter | 100% / 0.088 | 100% / 0.078 | 100% / 0.143 | 100% / 0.084 | 100% / 0.092 |
| log-dedup-regression | 100% / 0.103 | 100% / 0.068 | 100% / 0.126 | 100% / 0.102 | 100% / 0.086 |
| qa-cases-page-size | 100% / 0.032 | 100% / 0.040 | 100% / 0.082 | 100% / 0.058 | 100% / 0.035 |
| qa-default-dedup-window | 100% / 0.032 | 100% / 0.037 | 100% / 0.047 | 100% / 0.036 | 100% / 0.033 |
| qa-filter-overview | 100% / 0.089 | 100% / 0.098 | 100% / 0.130 | 100% / 0.086 | 100% / 0.070 |
| qa-history-dedup-config | 100% / 0.039 | 100% / 0.044 | 100% / 0.044 | 100% / 0.039 | 100% / 0.038 |
| qa-signal-pipeline | 100% / 0.063 | 100% / 0.064 | 100% / 0.118 | 100% / 0.057 | 100% / 0.063 |
| qa-ui-entity-stats | 100% / 0.045 | 100% / 0.048 | 100% / 0.125 | 100% / 0.069 | 100% / 0.047 |

## Run status per arm

| arm | ok | timeout | error | invalid |
|---|---|---|---|---|
| native | 10 | 0 | 0 | 0 |
| sobre | 10 | 0 | 0 | 0 |
| lean-ctx | 10 | 0 | 0 | 0 |
| headroom | 10 | 0 | 0 | 0 |
| rtk | 10 | 0 | 0 | 0 |

## Not scored or flagged

| run | status | reason |
|---|---|---|
| fix-snooze-expired-filter__rtk__r1 | ok, flagged | network_command |
| qa-default-dedup-window__rtk__r1 | ok, flagged | probe_inactive |
