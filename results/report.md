# sobre-bench report

100 scored runs (graded, or timed out or errored, which count as failures) out of 100. Bootstrap: 10000 resamples over tasks, seed 20261010. Non-inferiority margin: 5.0 percentage points of success. Cost: tokens x harness/prices.json (client estimate alongside).

## Per arm

| arm | runs | success | cost mean $ | cost median $ | client cost $ | input | output | cache read | cache write 5m | cache write 1h | turns | wall s | tool calls |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| native | 20 | 100.0% | 0.0645 | 0.0683 | 0.0552 | 10 | 1,633 | 92,667 | 11,833 | 0 | 5.2 | 25 | 4.2 |
| sobre | 20 | 100.0% | 0.0732 | 0.0710 | 0.0623 | 11 | 1,847 | 108,410 | 13,198 | 0 | 6.3 | 30 | 5.3 |
| lean-ctx | 20 | 100.0% | 0.1034 | 0.1169 | 0.0893 | 11 | 2,205 | 140,898 | 21,275 | 0 | 8.9 | 31 | 8.0 |
| headroom | 20 | 100.0% | 0.0715 | 0.0743 | 0.0623 | 10 | 1,666 | 92,234 | 14,548 | 0 | 5.6 | 26 | 4.6 |
| rtk | 20 | 100.0% | 0.0691 | 0.0604 | 0.0587 | 11 | 1,692 | 103,530 | 12,580 | 0 | 5.8 | 28 | 4.8 |

## Paired with native (per-task means over reps)

| arm | tasks | Δ success (pp) | 95% CI | cost ratio (geo mean) | 95% CI | success verdict |
|---|---|---|---|---|---|---|
| sobre | 10 | 0.0 | [0.0, 0.0] | 1.128 | [1.030, 1.253] | non-inferior |
| lean-ctx | 10 | 0.0 | [0.0, 0.0] | 1.594 | [1.416, 1.787] | non-inferior |
| headroom | 10 | 0.0 | [0.0, 0.0] | 1.120 | [1.045, 1.213] | non-inferior |
| rtk | 10 | 0.0 | [0.0, 0.0] | 1.062 | [1.007, 1.121] | non-inferior |

## Per task (success rate / mean cost $)

| task | native | sobre | lean-ctx | headroom | rtk |
|---|---|---|---|---|---|
| change-filter-reason | 100% / 0.099 | 100% / 0.109 | 100% / 0.155 | 100% / 0.102 | 100% / 0.103 |
| fix-signal-stats-scope | 100% / 0.078 | 100% / 0.129 | 100% / 0.129 | 100% / 0.105 | 100% / 0.095 |
| fix-snooze-expired-filter | 100% / 0.081 | 100% / 0.076 | 100% / 0.124 | 100% / 0.082 | 100% / 0.075 |
| log-dedup-regression | 100% / 0.097 | 100% / 0.087 | 100% / 0.121 | 100% / 0.096 | 100% / 0.119 |
| qa-cases-page-size | 100% / 0.033 | 100% / 0.038 | 100% / 0.063 | 100% / 0.045 | 100% / 0.034 |
| qa-default-dedup-window | 100% / 0.032 | 100% / 0.036 | 100% / 0.048 | 100% / 0.035 | 100% / 0.034 |
| qa-filter-overview | 100% / 0.083 | 100% / 0.089 | 100% / 0.158 | 100% / 0.092 | 100% / 0.081 |
| qa-history-dedup-config | 100% / 0.038 | 100% / 0.040 | 100% / 0.042 | 100% / 0.038 | 100% / 0.038 |
| qa-signal-pipeline | 100% / 0.059 | 100% / 0.076 | 100% / 0.099 | 100% / 0.062 | 100% / 0.060 |
| qa-ui-entity-stats | 100% / 0.045 | 100% / 0.051 | 100% / 0.095 | 100% / 0.057 | 100% / 0.052 |

## Run status per arm

| arm | ok | timeout | error | invalid |
|---|---|---|---|---|
| native | 20 | 0 | 0 | 0 |
| sobre | 20 | 0 | 0 | 0 |
| lean-ctx | 20 | 0 | 0 | 0 |
| headroom | 20 | 0 | 0 | 0 |
| rtk | 20 | 0 | 0 | 0 |

## Not scored or flagged

| run | status | reason |
|---|---|---|
| fix-snooze-expired-filter__rtk__r1 | ok, flagged | network_command |
| qa-default-dedup-window__rtk__r1 | ok, flagged | probe_inactive |
