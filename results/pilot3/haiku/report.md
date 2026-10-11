# sobre-bench report

157 scored runs (graded, or timed out or errored, which count as failures) out of 160. Bootstrap: 10000 resamples over tasks, seed 20261010. Non-inferiority margin: 5.0 percentage points of success. Cost: tokens x harness/prices.json (client estimate alongside).

## Per arm

| arm | runs | success | cost mean $ | cost median $ | client cost $ | input | output | cache read | cache write 5m | cache write 1h | turns | wall s | tool calls |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| native | 40 | 90.0% | 0.0211 | 0.0068 | 0.0211 | 47 | 14,014 | 815,974 | 47,042 | 0 | 15.6 | 91 | 14.0 |
| sobre-dev | 39 | 100.0% | 0.0230 | 0.0068 | 0.0230 | 51 | 14,384 | 950,723 | 50,037 | 0 | 16.0 | 109 | 14.4 |
| sobre-dev-06 | 39 | 94.9% | 0.0256 | 0.0075 | 0.0243 | 46 | 13,700 | 856,501 | 46,869 | 0 | 15.3 | 91 | 13.7 |
| sobre-dev-09 | 39 | 100.0% | 0.0237 | 0.0069 | 0.0237 | 50 | 15,524 | 958,344 | 51,193 | 0 | 15.7 | 107 | 14.1 |

## Paired with native (per-task means over reps)

| arm | tasks | Δ success (pp) | 95% CI | cost ratio (geo mean) | 95% CI | success verdict |
|---|---|---|---|---|---|---|
| sobre-dev | 20 | 10.0 | [2.5, 20.0] | 1.048 | [0.946, 1.150] | non-inferior |
| sobre-dev-06 | 20 | 5.0 | [-7.5, 17.5] | 1.020 | [0.902, 1.198] | inconclusive |
| sobre-dev-09 | 20 | 10.0 | [2.5, 20.0] | 1.023 | [0.932, 1.113] | non-inferior |

## Per task (success rate / mean cost $)

| task | native | sobre-dev | sobre-dev-06 | sobre-dev-09 |
|---|---|---|---|---|
| audit-unprotected-endpoints | 100% / 0.003 | 100% / 0.003 | 100% / 0.003 | 100% / 0.003 |
| change-filter-reason | 50% / 0.016 | 100% / 0.025 | 100% / 0.014 | 100% / 0.018 |
| ci-red-regressions | 50% / 0.010 | 100% / 0.005 | 100% / 0.006 | 100% / 0.006 |
| feature-signal-mute | 100% / 0.038 | 100% / 0.051 | 100% / 0.042 | 100% / 0.044 |
| fix-signal-stats-scope | 50% / 0.010 | 100% / 0.009 | 100% / 0.009 | 100% / 0.009 |
| fix-snooze-expired-filter | 100% / 0.006 | 100% / 0.006 | 50% / 0.006 | 100% / 0.005 |
| history-dedup-commits | 100% / 0.006 | 100% / 0.005 | 100% / 0.005 | 100% / 0.005 |
| log-dedup-regression | 100% / 0.008 | 100% / 0.012 | 100% / 0.011 | 100% / 0.011 |
| log-reminders-stopped | 100% / 0.007 | 100% / 0.007 | 100% / 0.007 | 100% / 0.006 |
| mt-dedup-snooze-regressions | 100% / 0.072 | 100% / 0.084 | 100% / 0.082 | 100% / 0.094 |
| mt-redaction-entities | 100% / 0.064 | 100% / 0.067 | 100% / 0.070 | 100% / 0.063 |
| mt-reminders-incident | 100% / 0.099 | 100% / 0.116 | 100% / 0.327 | 100% / 0.133 |
| mt-security-review | 100% / 0.048 | 100% / 0.046 | 50% / 0.048 | 100% / 0.048 |
| qa-cases-page-size | 100% / 0.003 | 100% / 0.003 | 100% / 0.002 | 100% / 0.003 |
| qa-default-dedup-window | 100% / 0.003 | 100% / 0.002 | 100% / 0.002 | 100% / 0.003 |
| qa-filter-overview | 100% / 0.006 | 100% / 0.007 | 100% / 0.008 | 100% / 0.008 |
| qa-history-dedup-config | 100% / 0.003 | 100% / 0.003 | 100% / 0.002 | 100% / 0.002 |
| qa-signal-pipeline | 100% / 0.005 | 100% / 0.006 | 100% / 0.005 | 100% / 0.005 |
| qa-ui-entity-stats | 100% / 0.004 | 100% / 0.004 | 100% / 0.004 | 100% / 0.004 |
| refactor-merge-action | 50% / 0.013 | 100% / 0.010 | 100% / 0.009 | 100% / 0.015 |

## Run status per arm

| arm | ok | timeout | error | invalid |
|---|---|---|---|---|
| native | 40 | 0 | 0 | 0 |
| sobre-dev | 39 | 0 | 0 | 1 |
| sobre-dev-06 | 39 | 0 | 0 | 1 |
| sobre-dev-09 | 39 | 0 | 0 | 1 |

## Not scored or flagged

| run | status | reason |
|---|---|---|
| change-filter-reason__sobre-dev-09__r1 | ok, flagged | network_command |
| feature-signal-mute__sobre-dev-09__r1 | invalid | its agent's `kill` loop over processes matching pytest also matched its own claude, whose argv then held the prompt; prompts now go in on stdin |
| feature-signal-mute__sobre-dev__r1 | invalid | killed by another run's agent (a `kill` loop over processes matching pytest) while runs overlapped without process isolation |
| feature-signal-mute__sobre-dev__r2 | ok, flagged | network_command |
| mt-reminders-incident__sobre-dev-06__r1 | invalid | killed by another run's agent (a `kill` loop over processes matching pytest) while runs overlapped without process isolation |
| refactor-merge-action__native__r1 | ok, flagged | network_command |
