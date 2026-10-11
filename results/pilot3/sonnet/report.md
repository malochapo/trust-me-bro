# sobre-bench report

208 scored runs (graded, or timed out or errored, which count as failures) out of 208. Bootstrap: 10000 resamples over tasks, seed 20261010. Non-inferiority margin: 5.0 percentage points of success. Cost: tokens x harness/prices.json (client estimate alongside).

## Per arm

| arm | runs | success | cost mean $ | cost median $ | client cost $ | input | output | cache read | cache write 5m | cache write 1h | turns | wall s | tool calls |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| native | 44 | 100.0% | 0.2475 | 0.0700 | 0.2475 | 39 | 8,264 | 577,959 | 42,810 | 0 | 10.0 | 66 | 8.2 |
| sobre-dev | 44 | 100.0% | 0.2342 | 0.0732 | 0.2342 | 39 | 7,859 | 549,238 | 40,233 | 0 | 10.0 | 75 | 8.2 |
| sobre-dev-06 | 40 | 100.0% | 0.1628 | 0.0651 | 0.1628 | 29 | 5,464 | 362,912 | 28,736 | 0 | 8.3 | 61 | 6.7 |
| sobre-dev-09 | 40 | 100.0% | 0.1539 | 0.0636 | 0.1539 | 28 | 5,209 | 324,448 | 27,728 | 0 | 8.1 | 59 | 6.5 |
| sobre-dev-09b | 40 | 100.0% | 0.1646 | 0.0637 | 0.1646 | 29 | 5,650 | 356,333 | 28,947 | 0 | 8.5 | 56 | 6.9 |

## Paired with native (per-task means over reps)

| arm | tasks | Δ success (pp) | 95% CI | cost ratio (geo mean) | 95% CI | success verdict |
|---|---|---|---|---|---|---|
| sobre-dev | 20 | 0.0 | [0.0, 0.0] | 1.027 | [0.976, 1.082] | non-inferior |
| sobre-dev-06 | 20 | 0.0 | [0.0, 0.0] | 0.997 | [0.948, 1.047] | non-inferior |
| sobre-dev-09 | 20 | 0.0 | [0.0, 0.0] | 0.980 | [0.912, 1.048] | non-inferior |
| sobre-dev-09b | 20 | 0.0 | [0.0, 0.0] | 0.993 | [0.950, 1.037] | non-inferior |

## Per task (success rate / mean cost $)

| task | native | sobre-dev | sobre-dev-06 | sobre-dev-09 | sobre-dev-09b |
|---|---|---|---|---|---|
| audit-unprotected-endpoints | 100% / 0.033 | 100% / 0.035 | 100% / 0.032 | 100% / 0.035 | 100% / 0.035 |
| change-filter-reason | 100% / 0.077 | 100% / 0.087 | 100% / 0.082 | 100% / 0.085 | 100% / 0.080 |
| ci-red-regressions | 100% / 0.056 | 100% / 0.054 | 100% / 0.055 | 100% / 0.062 | 100% / 0.054 |
| feature-signal-mute | 100% / 0.191 | 100% / 0.166 | 100% / 0.194 | 100% / 0.163 | 100% / 0.180 |
| fix-signal-stats-scope | 100% / 0.072 | 100% / 0.066 | 100% / 0.063 | 100% / 0.082 | 100% / 0.069 |
| fix-snooze-expired-filter | 100% / 0.066 | 100% / 0.065 | 100% / 0.067 | 100% / 0.057 | 100% / 0.060 |
| history-dedup-commits | 100% / 0.053 | 100% / 0.045 | 100% / 0.045 | 100% / 0.047 | 100% / 0.051 |
| log-dedup-regression | 100% / 0.089 | 100% / 0.084 | 100% / 0.071 | 100% / 0.072 | 100% / 0.076 |
| log-reminders-stopped | 100% / 0.087 | 100% / 0.079 | 100% / 0.089 | 100% / 0.065 | 100% / 0.070 |
| mt-dedup-snooze-regressions | 100% / 0.565 | 100% / 0.675 | 100% / 0.560 | 100% / 0.501 | 100% / 0.565 |
| mt-redaction-entities | 100% / 0.495 | 100% / 0.536 | 100% / 0.477 | 100% / 0.493 | 100% / 0.495 |
| mt-reminders-incident | 100% / 0.992 | 100% / 0.838 | 100% / 0.784 | 100% / 0.662 | 100% / 0.814 |
| mt-security-review | 100% / 0.390 | 100% / 0.405 | 100% / 0.406 | 100% / 0.431 | 100% / 0.422 |
| qa-cases-page-size | 100% / 0.028 | 100% / 0.029 | 100% / 0.029 | 100% / 0.030 | 100% / 0.031 |
| qa-default-dedup-window | 100% / 0.028 | 100% / 0.029 | 100% / 0.031 | 100% / 0.034 | 100% / 0.031 |
| qa-filter-overview | 100% / 0.063 | 100% / 0.084 | 100% / 0.076 | 100% / 0.075 | 100% / 0.071 |
| qa-history-dedup-config | 100% / 0.031 | 100% / 0.033 | 100% / 0.030 | 100% / 0.030 | 100% / 0.031 |
| qa-signal-pipeline | 100% / 0.050 | 100% / 0.054 | 100% / 0.050 | 100% / 0.052 | 100% / 0.057 |
| qa-ui-entity-stats | 100% / 0.039 | 100% / 0.045 | 100% / 0.042 | 100% / 0.043 | 100% / 0.043 |
| refactor-merge-action | 100% / 0.059 | 100% / 0.070 | 100% / 0.072 | 100% / 0.061 | 100% / 0.059 |

## Run status per arm

| arm | ok | timeout | error | invalid |
|---|---|---|---|---|
| native | 44 | 0 | 0 | 0 |
| sobre-dev | 44 | 0 | 0 | 0 |
| sobre-dev-06 | 40 | 0 | 0 | 0 |
| sobre-dev-09 | 40 | 0 | 0 | 0 |
| sobre-dev-09b | 40 | 0 | 0 | 0 |

## Not scored or flagged

None.
