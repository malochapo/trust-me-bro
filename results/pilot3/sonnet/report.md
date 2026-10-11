# sobre-bench report

143 scored runs (graded, or timed out or errored, which count as failures) out of 143. Bootstrap: 10000 resamples over tasks, seed 20261010. Non-inferiority margin: 5.0 percentage points of success. Cost: tokens x harness/prices.json (client estimate alongside).

## Per arm

| arm | runs | success | cost mean $ | cost median $ | client cost $ | input | output | cache read | cache write 5m | cache write 1h | turns | wall s | tool calls |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| native | 36 | 100.0% | 0.1218 | 0.0606 | 0.1218 | 21 | 4,148 | 249,644 | 22,136 | 0 | 7.4 | 46 | 6.1 |
| sobre-dev | 36 | 100.0% | 0.1248 | 0.0635 | 0.1248 | 22 | 4,134 | 269,778 | 22,562 | 0 | 7.6 | 56 | 6.3 |
| sobre-dev-06 | 36 | 100.0% | 0.1217 | 0.0620 | 0.1217 | 21 | 3,887 | 260,299 | 22,724 | 0 | 7.3 | 52 | 6.0 |
| sobre-dev-09 | 35 | 100.0% | 0.0973 | 0.0578 | 0.0973 | 18 | 3,251 | 193,418 | 18,145 | 0 | 6.8 | 48 | 5.6 |

## Paired with native (per-task means over reps)

| arm | tasks | Δ success (pp) | 95% CI | cost ratio (geo mean) | 95% CI | success verdict |
|---|---|---|---|---|---|---|
| sobre-dev | 20 | 0.0 | [0.0, 0.0] | 1.033 | [0.974, 1.099] | non-inferior |
| sobre-dev-06 | 20 | 0.0 | [0.0, 0.0] | 1.009 | [0.965, 1.054] | non-inferior |
| sobre-dev-09 | 19 | 0.0 | [0.0, 0.0] | 1.000 | [0.938, 1.061] | non-inferior |

## Per task (success rate / mean cost $)

| task | native | sobre-dev | sobre-dev-06 | sobre-dev-09 |
|---|---|---|---|---|
| audit-unprotected-endpoints | 100% / 0.033 | 100% / 0.035 | 100% / 0.032 | 100% / 0.035 |
| change-filter-reason | 100% / 0.077 | 100% / 0.087 | 100% / 0.082 | 100% / 0.085 |
| ci-red-regressions | 100% / 0.056 | 100% / 0.054 | 100% / 0.055 | 100% / 0.062 |
| feature-signal-mute | 100% / 0.191 | 100% / 0.166 | 100% / 0.194 | 100% / 0.163 |
| fix-signal-stats-scope | 100% / 0.072 | 100% / 0.066 | 100% / 0.063 | 100% / 0.082 |
| fix-snooze-expired-filter | 100% / 0.066 | 100% / 0.065 | 100% / 0.067 | 100% / 0.057 |
| history-dedup-commits | 100% / 0.053 | 100% / 0.045 | 100% / 0.045 | 100% / 0.047 |
| log-dedup-regression | 100% / 0.089 | 100% / 0.084 | 100% / 0.071 | 100% / 0.072 |
| log-reminders-stopped | 100% / 0.087 | 100% / 0.079 | 100% / 0.089 | 100% / 0.065 |
| mt-dedup-snooze-regressions | 100% / 0.562 | 100% / 0.782 | 100% / 0.558 | 100% / 0.483 |
| mt-redaction-entities | 100% / 0.476 | 100% / 0.502 | 100% / 0.494 | 100% / 0.473 |
| mt-reminders-incident | 100% / 0.898 | 100% / 0.719 | 100% / 0.857 | - |
| mt-security-review | 100% / 0.408 | 100% / 0.443 | 100% / 0.416 | 100% / 0.465 |
| qa-cases-page-size | 100% / 0.028 | 100% / 0.029 | 100% / 0.029 | 100% / 0.030 |
| qa-default-dedup-window | 100% / 0.028 | 100% / 0.029 | 100% / 0.031 | 100% / 0.034 |
| qa-filter-overview | 100% / 0.063 | 100% / 0.084 | 100% / 0.076 | 100% / 0.075 |
| qa-history-dedup-config | 100% / 0.031 | 100% / 0.033 | 100% / 0.030 | 100% / 0.030 |
| qa-signal-pipeline | 100% / 0.050 | 100% / 0.054 | 100% / 0.050 | 100% / 0.052 |
| qa-ui-entity-stats | 100% / 0.039 | 100% / 0.045 | 100% / 0.042 | 100% / 0.043 |
| refactor-merge-action | 100% / 0.059 | 100% / 0.070 | 100% / 0.072 | 100% / 0.061 |

## Run status per arm

| arm | ok | timeout | error | invalid |
|---|---|---|---|---|
| native | 36 | 0 | 0 | 0 |
| sobre-dev | 36 | 0 | 0 | 0 |
| sobre-dev-06 | 36 | 0 | 0 | 0 |
| sobre-dev-09 | 35 | 0 | 0 | 0 |

## Not scored or flagged

None.
