# sobre-bench report

84 scored runs (graded, or timed out or errored, which count as failures) out of 84. Bootstrap: 10000 resamples over tasks, seed 20261010. Non-inferiority margin: 5.0 percentage points of success. Cost: tokens x harness/prices.json (client estimate alongside).

## Per arm

| arm | runs | success | cost mean $ | cost median $ | client cost $ | input | output | cache read | cache write 5m | cache write 1h | turns | wall s | tool calls |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| native | 12 | 100.0% | 0.0912 | 0.0725 | 0.0771 | 13 | 2,458 | 140,288 | 15,397 | 0 | 7.0 | 50 | 6.0 |
| sobre | 12 | 100.0% | 0.1072 | 0.0658 | 0.0881 | 15 | 2,885 | 190,287 | 16,087 | 0 | 7.8 | 69 | 6.8 |
| sobre-dev | 12 | 100.0% | 0.0931 | 0.0687 | 0.0787 | 13 | 2,347 | 144,533 | 16,295 | 0 | 6.9 | 51 | 5.9 |
| sobre-hooks | 12 | 100.0% | 0.0876 | 0.0719 | 0.0744 | 12 | 2,482 | 131,306 | 14,585 | 0 | 6.7 | 53 | 5.7 |
| lean-ctx | 12 | 100.0% | 0.1658 | 0.1154 | 0.1412 | 16 | 3,205 | 246,391 | 33,793 | 0 | 11.0 | 53 | 10.0 |
| headroom | 12 | 100.0% | 0.1138 | 0.0870 | 0.0995 | 14 | 2,475 | 142,966 | 24,176 | 0 | 7.0 | 55 | 6.0 |
| rtk | 12 | 100.0% | 0.1014 | 0.0770 | 0.0846 | 16 | 2,917 | 168,379 | 15,428 | 0 | 8.2 | 53 | 7.2 |

## Paired with native (per-task means over reps)

| arm | tasks | Δ success (pp) | 95% CI | cost ratio (geo mean) | 95% CI | success verdict |
|---|---|---|---|---|---|---|
| sobre | 6 | 0.0 | [0.0, 0.0] | 1.086 | [0.952, 1.266] | non-inferior |
| sobre-dev | 6 | 0.0 | [0.0, 0.0] | 1.005 | [0.908, 1.106] | non-inferior |
| sobre-hooks | 6 | 0.0 | [0.0, 0.0] | 0.967 | [0.823, 1.077] | non-inferior |
| lean-ctx | 6 | 0.0 | [0.0, 0.0] | 1.769 | [1.488, 2.072] | non-inferior |
| headroom | 6 | 0.0 | [0.0, 0.0] | 1.251 | [1.169, 1.352] | non-inferior |
| rtk | 6 | 0.0 | [0.0, 0.0] | 1.116 | [0.917, 1.477] | non-inferior |

## Per task (success rate / mean cost $)

| task | native | sobre | sobre-dev | sobre-hooks | lean-ctx | headroom | rtk |
|---|---|---|---|---|---|---|---|
| audit-unprotected-endpoints | 100% / 0.038 | 100% / 0.048 | 100% / 0.044 | 100% / 0.040 | 100% / 0.086 | 100% / 0.049 | 100% / 0.043 |
| ci-red-regressions | 100% / 0.066 | 100% / 0.065 | 100% / 0.070 | 100% / 0.068 | 100% / 0.128 | 100% / 0.086 | 100% / 0.142 |
| feature-signal-mute | 100% / 0.198 | 100% / 0.291 | 100% / 0.226 | 100% / 0.204 | 100% / 0.429 | 100% / 0.230 | 100% / 0.201 |
| history-dedup-commits | 100% / 0.056 | 100% / 0.057 | 100% / 0.056 | 100% / 0.064 | 100% / 0.098 | 100% / 0.066 | 100% / 0.053 |
| log-reminders-stopped | 100% / 0.111 | 100% / 0.115 | 100% / 0.097 | 100% / 0.073 | 100% / 0.139 | 100% / 0.164 | 100% / 0.092 |
| refactor-merge-action | 100% / 0.078 | 100% / 0.067 | 100% / 0.066 | 100% / 0.076 | 100% / 0.115 | 100% / 0.088 | 100% / 0.077 |

## Run status per arm

| arm | ok | timeout | error | invalid |
|---|---|---|---|---|
| native | 12 | 0 | 0 | 0 |
| sobre | 12 | 0 | 0 | 0 |
| sobre-dev | 12 | 0 | 0 | 0 |
| sobre-hooks | 12 | 0 | 0 | 0 |
| lean-ctx | 12 | 0 | 0 | 0 |
| headroom | 12 | 0 | 0 | 0 |
| rtk | 12 | 0 | 0 | 0 |

## Not scored or flagged

| run | status | reason |
|---|---|---|
| ci-red-regressions__rtk__r1 | ok, flagged | network_command |
