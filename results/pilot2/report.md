# sobre-bench report

36 scored runs (graded, or timed out or errored, which count as failures) out of 36. Bootstrap: 10000 resamples over tasks, seed 20261010. Non-inferiority margin: 5.0 percentage points of success. Cost: tokens x harness/prices.json (client estimate alongside).

## Per arm

| arm | runs | success | cost mean $ | cost median $ | client cost $ | input | output | cache read | cache write 5m | cache write 1h | turns | wall s | tool calls |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| native | 6 | 100.0% | 0.0976 | 0.0711 | 0.0822 | 14 | 2,596 | 154,805 | 16,278 | 0 | 7.5 | 54 | 6.5 |
| sobre | 6 | 100.0% | 0.1121 | 0.0689 | 0.0930 | 16 | 3,149 | 191,740 | 16,906 | 0 | 8.2 | 60 | 7.2 |
| sobre-dev | 6 | 100.0% | 0.1020 | 0.0687 | 0.0866 | 13 | 2,564 | 154,146 | 18,196 | 0 | 7.2 | 54 | 6.2 |
| lean-ctx | 6 | 100.0% | 0.1621 | 0.1108 | 0.1360 | 16 | 3,282 | 261,330 | 30,808 | 0 | 11.2 | 51 | 10.2 |
| headroom | 6 | 100.0% | 0.1192 | 0.0878 | 0.1045 | 14 | 2,544 | 147,154 | 25,734 | 0 | 7.0 | 58 | 6.0 |
| rtk | 6 | 100.0% | 0.0954 | 0.0714 | 0.0799 | 15 | 2,796 | 154,324 | 14,599 | 0 | 7.8 | 49 | 6.8 |

## Paired with native (per-task means over reps)

| arm | tasks | Δ success (pp) | 95% CI | cost ratio (geo mean) | 95% CI | success verdict |
|---|---|---|---|---|---|---|
| sobre | 6 | 0.0 | [0.0, 0.0] | 1.119 | [1.016, 1.225] | non-inferior |
| sobre-dev | 6 | 0.0 | [0.0, 0.0] | 1.028 | [0.936, 1.125] | non-inferior |
| lean-ctx | 6 | 0.0 | [0.0, 0.0] | 1.570 | [1.147, 1.970] | non-inferior |
| headroom | 6 | 0.0 | [0.0, 0.0] | 1.209 | [1.089, 1.322] | non-inferior |
| rtk | 6 | 0.0 | [0.0, 0.0] | 0.997 | [0.684, 1.376] | non-inferior |

## Per task (success rate / mean cost $)

| task | native | sobre | sobre-dev | lean-ctx | headroom | rtk |
|---|---|---|---|---|---|---|
| audit-unprotected-endpoints | 100% / 0.038 | 100% / 0.048 | 100% / 0.040 | 100% / 0.066 | 100% / 0.037 | 100% / 0.047 |
| ci-red-regressions | 100% / 0.064 | 100% / 0.063 | 100% / 0.068 | 100% / 0.118 | 100% / 0.087 | 100% / 0.119 |
| feature-signal-mute | 100% / 0.216 | 100% / 0.268 | 100% / 0.253 | 100% / 0.465 | 100% / 0.253 | 100% / 0.213 |
| history-dedup-commits | 100% / 0.055 | 100% / 0.065 | 100% / 0.063 | 100% / 0.108 | 100% / 0.075 | 100% / 0.051 |
| log-reminders-stopped | 100% / 0.135 | 100% / 0.156 | 100% / 0.118 | 100% / 0.101 | 100% / 0.175 | 100% / 0.060 |
| refactor-merge-action | 100% / 0.079 | 100% / 0.073 | 100% / 0.070 | 100% / 0.114 | 100% / 0.089 | 100% / 0.083 |

## Run status per arm

| arm | ok | timeout | error | invalid |
|---|---|---|---|---|
| native | 6 | 0 | 0 | 0 |
| sobre | 6 | 0 | 0 | 0 |
| sobre-dev | 6 | 0 | 0 | 0 |
| lean-ctx | 6 | 0 | 0 | 0 |
| headroom | 6 | 0 | 0 | 0 |
| rtk | 6 | 0 | 0 | 0 |

## Not scored or flagged

| run | status | reason |
|---|---|---|
| ci-red-regressions__rtk__r1 | ok, flagged | network_command |
