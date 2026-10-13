# trust-me-bro report

84 scored runs (graded, or timed out or errored, which count as failures) out of 84. Bootstrap: 10000 resamples over tasks, seed 20261010. Non-inferiority margin: 5.0 percentage points of success. Cost: tokens x harness/prices.json (client estimate alongside). Cold start: the same runs, each session priced as if it had started with a cold prompt cache (docs/cache-isolation.md).

## Per arm

| arm | runs | success | cost mean $ | cost median $ | cold-start cost mean $ | client cost $ | input | output | cache read | cache write 5m | cache write 1h | turns | wall s | tool calls |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| native | 12 | 100.0% | 0.0771 | 0.0608 | 0.1038 | 0.0771 | 13 | 2,458 | 140,288 | 15,397 | 0 | 7.0 | 50 | 6.0 |
| sobre | 12 | 100.0% | 0.0881 | 0.0559 | 0.1148 | 0.0881 | 15 | 2,885 | 190,287 | 16,087 | 0 | 7.8 | 69 | 6.8 |
| sobre-dev | 12 | 100.0% | 0.0787 | 0.0586 | 0.1053 | 0.0787 | 13 | 2,347 | 144,533 | 16,295 | 0 | 6.9 | 51 | 5.9 |
| sobre-hooks | 12 | 100.0% | 0.0744 | 0.0620 | 0.1011 | 0.0744 | 12 | 2,482 | 131,306 | 14,585 | 0 | 6.7 | 53 | 5.7 |
| lean-ctx | 12 | 100.0% | 0.1412 | 0.1003 | 0.1474 | 0.1412 | 16 | 3,205 | 246,391 | 33,793 | 0 | 11.0 | 53 | 10.0 |
| headroom | 12 | 100.0% | 0.0995 | 0.0788 | 0.1056 | 0.0995 | 14 | 2,475 | 142,966 | 24,176 | 0 | 7.0 | 55 | 6.0 |
| rtk | 12 | 100.0% | 0.0846 | 0.0661 | 0.1113 | 0.0846 | 16 | 2,917 | 168,379 | 15,428 | 0 | 8.2 | 53 | 7.2 |

## Paired with native (per-task means over reps)

| arm | tasks | Δ success (pp) | 95% CI | cost ratio (geo mean) | 95% CI | cold-start cost ratio | 95% CI | success verdict |
|---|---|---|---|---|---|---|---|---|
| sobre | 6 | 0.0 | [0.0, 0.0] | 1.076 | [0.960, 1.229] | 1.058 | [0.971, 1.185] | non-inferior |
| sobre-dev | 6 | 0.0 | [0.0, 0.0] | 1.011 | [0.920, 1.102] | 1.006 | [0.941, 1.070] | non-inferior |
| sobre-hooks | 6 | 0.0 | [0.0, 0.0] | 0.974 | [0.827, 1.088] | 0.977 | [0.867, 1.058] | non-inferior |
| lean-ctx | 6 | 0.0 | [0.0, 0.0] | 1.805 | [1.516, 2.110] | 1.346 | [1.157, 1.579] | non-inferior |
| headroom | 6 | 0.0 | [0.0, 0.0] | 1.304 | [1.222, 1.395] | 0.991 | [0.915, 1.098] | non-inferior |
| rtk | 6 | 0.0 | [0.0, 0.0] | 1.104 | [0.914, 1.440] | 1.073 | [0.932, 1.312] | non-inferior |

## Per task (success rate / mean cost $)

| task | native | sobre | sobre-dev | sobre-hooks | lean-ctx | headroom | rtk |
|---|---|---|---|---|---|---|---|
| audit-unprotected-endpoints | 100% / 0.033 | 100% / 0.041 | 100% / 0.038 | 100% / 0.035 | 100% / 0.076 | 100% / 0.045 | 100% / 0.038 |
| ci-red-regressions | 100% / 0.054 | 100% / 0.054 | 100% / 0.059 | 100% / 0.057 | 100% / 0.111 | 100% / 0.077 | 100% / 0.112 |
| feature-signal-mute | 100% / 0.163 | 100% / 0.228 | 100% / 0.183 | 100% / 0.170 | 100% / 0.348 | 100% / 0.193 | 100% / 0.168 |
| history-dedup-commits | 100% / 0.049 | 100% / 0.049 | 100% / 0.048 | 100% / 0.056 | 100% / 0.089 | 100% / 0.060 | 100% / 0.046 |
| log-reminders-stopped | 100% / 0.097 | 100% / 0.096 | 100% / 0.087 | 100% / 0.063 | 100% / 0.123 | 100% / 0.142 | 100% / 0.079 |
| refactor-merge-action | 100% / 0.067 | 100% / 0.059 | 100% / 0.057 | 100% / 0.065 | 100% / 0.100 | 100% / 0.081 | 100% / 0.066 |

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
