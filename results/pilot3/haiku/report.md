# sobre-bench report

240 scored runs (graded, or timed out or errored, which count as failures) out of 240. Bootstrap: 10000 resamples over tasks, seed 20261010. Non-inferiority margin: 5.0 percentage points of success. Cost: tokens x harness/prices.json (client estimate alongside).

## Per arm

| arm | runs | success | cost mean $ | cost median $ | client cost $ | input | output | cache read | cache write 5m | cache write 1h | turns | wall s | tool calls |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| native | 40 | 100.0% | 0.0206 | 0.0063 | 0.0206 | 46 | 13,776 | 790,159 | 46,414 | 0 | 14.9 | 89 | 13.3 |
| sobre-dev | 40 | 100.0% | 0.0235 | 0.0069 | 0.0235 | 52 | 14,690 | 980,358 | 50,594 | 0 | 16.8 | 113 | 15.2 |
| sobre-dev-06 | 40 | 95.0% | 0.0278 | 0.0075 | 0.0266 | 49 | 14,909 | 971,308 | 51,526 | 0 | 16.0 | 97 | 14.4 |
| sobre-dev-09 | 40 | 100.0% | 0.0242 | 0.0072 | 0.0242 | 51 | 15,789 | 986,634 | 51,738 | 0 | 16.4 | 111 | 14.8 |
| sobre-dev-09b | 40 | 100.0% | 0.0239 | 0.0066 | 0.0240 | 50 | 15,337 | 965,750 | 50,385 | 0 | 16.4 | 108 | 14.8 |
| sobre-hooks | 40 | 97.5% | 0.0229 | 0.0081 | 0.0229 | 50 | 14,793 | 930,710 | 49,481 | 0 | 16.6 | 114 | 15.1 |

## Paired with native (per-task means over reps)

| arm | tasks | Δ success (pp) | 95% CI | cost ratio (geo mean) | 95% CI | success verdict |
|---|---|---|---|---|---|---|
| sobre-dev | 20 | 0.0 | [0.0, 0.0] | 1.097 | [1.020, 1.189] | non-inferior |
| sobre-dev-06 | 20 | -5.0 | [-12.5, 0.0] | 1.051 | [0.961, 1.169] | inconclusive |
| sobre-dev-09 | 20 | 0.0 | [0.0, 0.0] | 1.074 | [1.005, 1.146] | non-inferior |
| sobre-dev-09b | 20 | 0.0 | [0.0, 0.0] | 1.054 | [0.991, 1.126] | non-inferior |
| sobre-hooks | 20 | -2.5 | [-7.5, 0.0] | 1.110 | [1.019, 1.214] | inconclusive |

## Per task (success rate / mean cost $)

| task | native | sobre-dev | sobre-dev-06 | sobre-dev-09 | sobre-dev-09b | sobre-hooks |
|---|---|---|---|---|---|---|
| audit-unprotected-endpoints | 100% / 0.003 | 100% / 0.003 | 100% / 0.003 | 100% / 0.003 | 100% / 0.003 | 100% / 0.004 |
| change-filter-reason | 100% / 0.014 | 100% / 0.025 | 100% / 0.014 | 100% / 0.018 | 100% / 0.015 | 100% / 0.026 |
| ci-red-regressions | 100% / 0.006 | 100% / 0.005 | 100% / 0.006 | 100% / 0.006 | 100% / 0.006 | 100% / 0.006 |
| feature-signal-mute | 100% / 0.038 | 100% / 0.047 | 100% / 0.042 | 100% / 0.044 | 100% / 0.060 | 50% / 0.044 |
| fix-signal-stats-scope | 100% / 0.008 | 100% / 0.009 | 100% / 0.009 | 100% / 0.009 | 100% / 0.009 | 100% / 0.008 |
| fix-snooze-expired-filter | 100% / 0.006 | 100% / 0.006 | 50% / 0.006 | 100% / 0.005 | 100% / 0.006 | 100% / 0.007 |
| history-dedup-commits | 100% / 0.006 | 100% / 0.005 | 100% / 0.005 | 100% / 0.005 | 100% / 0.005 | 100% / 0.006 |
| log-dedup-regression | 100% / 0.009 | 100% / 0.012 | 100% / 0.011 | 100% / 0.011 | 100% / 0.008 | 100% / 0.011 |
| log-reminders-stopped | 100% / 0.006 | 100% / 0.007 | 100% / 0.007 | 100% / 0.006 | 100% / 0.007 | 100% / 0.009 |
| mt-dedup-snooze-regressions | 100% / 0.072 | 100% / 0.084 | 100% / 0.082 | 100% / 0.094 | 100% / 0.092 | 100% / 0.091 |
| mt-redaction-entities | 100% / 0.064 | 100% / 0.067 | 100% / 0.070 | 100% / 0.063 | 100% / 0.061 | 100% / 0.063 |
| mt-reminders-incident | 100% / 0.099 | 100% / 0.116 | 100% / 0.221 | 100% / 0.133 | 100% / 0.114 | 100% / 0.098 |
| mt-security-review | 100% / 0.048 | 100% / 0.046 | 50% / 0.048 | 100% / 0.048 | 100% / 0.059 | 100% / 0.049 |
| qa-cases-page-size | 100% / 0.002 | 100% / 0.003 | 100% / 0.002 | 100% / 0.003 | 100% / 0.003 | 100% / 0.003 |
| qa-default-dedup-window | 100% / 0.003 | 100% / 0.002 | 100% / 0.002 | 100% / 0.003 | 100% / 0.002 | 100% / 0.002 |
| qa-filter-overview | 100% / 0.006 | 100% / 0.007 | 100% / 0.008 | 100% / 0.008 | 100% / 0.006 | 100% / 0.009 |
| qa-history-dedup-config | 100% / 0.003 | 100% / 0.003 | 100% / 0.002 | 100% / 0.002 | 100% / 0.002 | 100% / 0.002 |
| qa-signal-pipeline | 100% / 0.005 | 100% / 0.006 | 100% / 0.005 | 100% / 0.005 | 100% / 0.004 | 100% / 0.005 |
| qa-ui-entity-stats | 100% / 0.005 | 100% / 0.004 | 100% / 0.004 | 100% / 0.004 | 100% / 0.004 | 100% / 0.004 |
| refactor-merge-action | 100% / 0.011 | 100% / 0.010 | 100% / 0.009 | 100% / 0.015 | 100% / 0.011 | 100% / 0.011 |

## Run status per arm

| arm | ok | timeout | error | invalid |
|---|---|---|---|---|
| native | 40 | 0 | 0 | 0 |
| sobre-dev | 40 | 0 | 0 | 0 |
| sobre-dev-06 | 40 | 0 | 0 | 0 |
| sobre-dev-09 | 40 | 0 | 0 | 0 |
| sobre-dev-09b | 40 | 0 | 0 | 0 |
| sobre-hooks | 40 | 0 | 0 | 0 |

## Not scored or flagged

| run | status | reason |
|---|---|---|
| change-filter-reason__sobre-dev-09__r1 | ok, flagged | network_command |
| change-filter-reason__sobre-dev-09b__r2 | ok, flagged | network_command |
| feature-signal-mute__sobre-dev__r2 | ok, flagged | network_command |
| feature-signal-mute__sobre-hooks__r2 | ok, flagged | network_command |
