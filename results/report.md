# trust-me-bro report

140 scored runs (graded, or timed out or errored, which count as failures) out of 140. Bootstrap: 10000 resamples over tasks, seed 20261010. Non-inferiority margin: 5.0 percentage points of success. Cost: tokens x harness/prices.json (client estimate alongside). Cold start: the same runs, each session priced as if it had started with a cold prompt cache (docs/cache-isolation.md).

## Per arm

| arm | runs | success | cost mean $ | cost median $ | cold-start cost mean $ | client cost $ | input | output | cache read | cache write 5m | cache write 1h | turns | wall s | tool calls |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| native | 20 | 100.0% | 0.0552 | 0.0578 | 0.0818 | 0.0552 | 10 | 1,633 | 92,667 | 11,833 | 0 | 5.2 | 25 | 4.2 |
| sobre | 20 | 100.0% | 0.0623 | 0.0619 | 0.0890 | 0.0623 | 11 | 1,847 | 108,410 | 13,198 | 0 | 6.3 | 30 | 5.3 |
| sobre-dev | 20 | 100.0% | 0.0557 | 0.0576 | 0.0824 | 0.0557 | 9 | 1,613 | 87,215 | 12,341 | 0 | 5.1 | 24 | 4.1 |
| sobre-hooks | 20 | 100.0% | 0.0575 | 0.0560 | 0.0842 | 0.0575 | 11 | 1,712 | 101,690 | 12,086 | 0 | 5.7 | 23 | 4.7 |
| lean-ctx | 20 | 100.0% | 0.0893 | 0.0959 | 0.1154 | 0.0893 | 11 | 2,205 | 140,898 | 21,275 | 0 | 8.9 | 31 | 8.0 |
| headroom | 20 | 100.0% | 0.0623 | 0.0646 | 0.0818 | 0.0623 | 10 | 1,666 | 92,234 | 14,548 | 0 | 5.6 | 26 | 4.6 |
| rtk | 20 | 100.0% | 0.0587 | 0.0520 | 0.0854 | 0.0587 | 11 | 1,692 | 103,530 | 12,580 | 0 | 5.8 | 28 | 4.8 |

## Paired with native (per-task means over reps)

| arm | tasks | Δ success (pp) | 95% CI | cost ratio (geo mean) | 95% CI | cold-start cost ratio | 95% CI | success verdict |
|---|---|---|---|---|---|---|---|---|
| sobre | 10 | 0.0 | [0.0, 0.0] | 1.127 | [1.040, 1.239] | 1.083 | [1.021, 1.163] | non-inferior |
| sobre-dev | 10 | 0.0 | [0.0, 0.0] | 1.020 | [0.974, 1.072] | 1.010 | [0.981, 1.043] | non-inferior |
| sobre-hooks | 10 | 0.0 | [0.0, 0.0] | 1.026 | [0.980, 1.078] | 1.020 | [0.988, 1.058] | non-inferior |
| lean-ctx | 10 | 0.0 | [0.0, 0.0] | 1.616 | [1.432, 1.820] | 1.405 | [1.314, 1.490] | non-inferior |
| headroom | 10 | 0.0 | [0.0, 0.0] | 1.142 | [1.057, 1.249] | 0.998 | [0.969, 1.030] | non-inferior |
| rtk | 10 | 0.0 | [0.0, 0.0] | 1.058 | [1.006, 1.113] | 1.039 | [1.003, 1.078] | non-inferior |

## Per task (success rate / mean cost $)

| task | native | sobre | sobre-dev | sobre-hooks | lean-ctx | headroom | rtk |
|---|---|---|---|---|---|---|---|
| change-filter-reason | 100% / 0.086 | 100% / 0.093 | 100% / 0.083 | 100% / 0.083 | 100% / 0.129 | 100% / 0.091 | 100% / 0.089 |
| fix-signal-stats-scope | 100% / 0.065 | 100% / 0.104 | 100% / 0.075 | 100% / 0.075 | 100% / 0.105 | 100% / 0.089 | 100% / 0.079 |
| fix-snooze-expired-filter | 100% / 0.066 | 100% / 0.064 | 100% / 0.062 | 100% / 0.065 | 100% / 0.106 | 100% / 0.067 | 100% / 0.062 |
| log-dedup-regression | 100% / 0.083 | 100% / 0.075 | 100% / 0.081 | 100% / 0.099 | 100% / 0.104 | 100% / 0.082 | 100% / 0.099 |
| qa-cases-page-size | 100% / 0.028 | 100% / 0.033 | 100% / 0.029 | 100% / 0.028 | 100% / 0.057 | 100% / 0.041 | 100% / 0.030 |
| qa-default-dedup-window | 100% / 0.028 | 100% / 0.032 | 100% / 0.032 | 100% / 0.028 | 100% / 0.041 | 100% / 0.031 | 100% / 0.030 |
| qa-filter-overview | 100% / 0.074 | 100% / 0.079 | 100% / 0.070 | 100% / 0.078 | 100% / 0.140 | 100% / 0.083 | 100% / 0.072 |
| qa-history-dedup-config | 100% / 0.032 | 100% / 0.034 | 100% / 0.030 | 100% / 0.030 | 100% / 0.036 | 100% / 0.032 | 100% / 0.032 |
| qa-signal-pipeline | 100% / 0.051 | 100% / 0.066 | 100% / 0.054 | 100% / 0.048 | 100% / 0.091 | 100% / 0.055 | 100% / 0.052 |
| qa-ui-entity-stats | 100% / 0.039 | 100% / 0.043 | 100% / 0.041 | 100% / 0.040 | 100% / 0.084 | 100% / 0.051 | 100% / 0.044 |

## Run status per arm

| arm | ok | timeout | error | invalid |
|---|---|---|---|---|
| native | 20 | 0 | 0 | 0 |
| sobre | 20 | 0 | 0 | 0 |
| sobre-dev | 20 | 0 | 0 | 0 |
| sobre-hooks | 20 | 0 | 0 | 0 |
| lean-ctx | 20 | 0 | 0 | 0 |
| headroom | 20 | 0 | 0 | 0 |
| rtk | 20 | 0 | 0 | 0 |

## Not scored or flagged

| run | status | reason |
|---|---|---|
| fix-snooze-expired-filter__rtk__r1 | ok, flagged | network_command |
| qa-default-dedup-window__rtk__r1 | ok, flagged | probe_inactive |
