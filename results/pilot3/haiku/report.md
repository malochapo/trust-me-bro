# sobre-bench report

280 scored runs (graded, or timed out or errored, which count as failures) out of 280. Bootstrap: 10000 resamples over tasks, seed 20261010. Non-inferiority margin: 5.0 percentage points of success. Cost: tokens x harness/prices.json (client estimate alongside).

## Per arm

| arm | runs | success | cost mean $ | cost median $ | client cost $ | input | output | cache read | cache write 5m | cache write 1h | turns | wall s | tool calls |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| native | 40 | 100.0% | 0.0206 | 0.0063 | 0.0206 | 46 | 13,776 | 790,159 | 46,414 | 0 | 14.9 | 89 | 13.3 |
| sobre-dev | 40 | 100.0% | 0.0235 | 0.0069 | 0.0235 | 52 | 14,690 | 980,358 | 50,594 | 0 | 16.8 | 113 | 15.2 |
| sobre-dev-06 | 40 | 95.0% | 0.0278 | 0.0075 | 0.0266 | 49 | 14,909 | 971,308 | 51,526 | 0 | 16.0 | 97 | 14.4 |
| sobre-dev-09 | 40 | 100.0% | 0.0242 | 0.0072 | 0.0242 | 51 | 15,789 | 986,634 | 51,738 | 0 | 16.4 | 111 | 14.8 |
| sobre-dev-09b | 40 | 100.0% | 0.0239 | 0.0066 | 0.0240 | 50 | 15,337 | 965,750 | 50,385 | 0 | 16.4 | 108 | 14.8 |
| sobre-hooks | 40 | 97.5% | 0.0229 | 0.0081 | 0.0229 | 50 | 14,793 | 930,710 | 49,481 | 0 | 16.6 | 114 | 15.1 |
| sobre-keyonly | 40 | 100.0% | 0.0227 | 0.0075 | 0.0227 | 48 | 15,005 | 899,365 | 49,549 | 0 | 15.9 | 86 | 14.3 |

## Paired with native (per-task means over reps)

| arm | tasks | Δ success (pp) | 95% CI | cost ratio (geo mean) | 95% CI | success verdict |
|---|---|---|---|---|---|---|
| sobre-dev | 20 | 0.0 | [0.0, 0.0] | 1.097 | [1.020, 1.189] | non-inferior |
| sobre-dev-06 | 20 | -5.0 | [-12.5, 0.0] | 1.051 | [0.961, 1.169] | inconclusive |
| sobre-dev-09 | 20 | 0.0 | [0.0, 0.0] | 1.074 | [1.005, 1.146] | non-inferior |
| sobre-dev-09b | 20 | 0.0 | [0.0, 0.0] | 1.054 | [0.991, 1.126] | non-inferior |
| sobre-hooks | 20 | -2.5 | [-7.5, 0.0] | 1.110 | [1.019, 1.214] | inconclusive |
| sobre-keyonly | 20 | 0.0 | [0.0, 0.0] | 1.034 | [0.963, 1.121] | non-inferior |

## Per task (success rate / mean cost $)

| task | native | sobre-dev | sobre-dev-06 | sobre-dev-09 | sobre-dev-09b | sobre-hooks | sobre-keyonly |
|---|---|---|---|---|---|---|---|
| audit-unprotected-endpoints | 100% / 0.003 | 100% / 0.003 | 100% / 0.003 | 100% / 0.003 | 100% / 0.003 | 100% / 0.004 | 100% / 0.003 |
| change-filter-reason | 100% / 0.014 | 100% / 0.025 | 100% / 0.014 | 100% / 0.018 | 100% / 0.015 | 100% / 0.026 | 100% / 0.012 |
| ci-red-regressions | 100% / 0.006 | 100% / 0.005 | 100% / 0.006 | 100% / 0.006 | 100% / 0.006 | 100% / 0.006 | 100% / 0.006 |
| feature-signal-mute | 100% / 0.038 | 100% / 0.047 | 100% / 0.042 | 100% / 0.044 | 100% / 0.060 | 50% / 0.044 | 100% / 0.045 |
| fix-signal-stats-scope | 100% / 0.008 | 100% / 0.009 | 100% / 0.009 | 100% / 0.009 | 100% / 0.009 | 100% / 0.008 | 100% / 0.009 |
| fix-snooze-expired-filter | 100% / 0.006 | 100% / 0.006 | 50% / 0.006 | 100% / 0.005 | 100% / 0.006 | 100% / 0.007 | 100% / 0.007 |
| history-dedup-commits | 100% / 0.006 | 100% / 0.005 | 100% / 0.005 | 100% / 0.005 | 100% / 0.005 | 100% / 0.006 | 100% / 0.005 |
| log-dedup-regression | 100% / 0.009 | 100% / 0.012 | 100% / 0.011 | 100% / 0.011 | 100% / 0.008 | 100% / 0.011 | 100% / 0.009 |
| log-reminders-stopped | 100% / 0.006 | 100% / 0.007 | 100% / 0.007 | 100% / 0.006 | 100% / 0.007 | 100% / 0.009 | 100% / 0.009 |
| mt-dedup-snooze-regressions | 100% / 0.072 | 100% / 0.084 | 100% / 0.082 | 100% / 0.094 | 100% / 0.092 | 100% / 0.091 | 100% / 0.116 |
| mt-redaction-entities | 100% / 0.064 | 100% / 0.067 | 100% / 0.070 | 100% / 0.063 | 100% / 0.061 | 100% / 0.063 | 100% / 0.065 |
| mt-reminders-incident | 100% / 0.099 | 100% / 0.116 | 100% / 0.221 | 100% / 0.133 | 100% / 0.114 | 100% / 0.098 | 100% / 0.091 |
| mt-security-review | 100% / 0.048 | 100% / 0.046 | 50% / 0.048 | 100% / 0.048 | 100% / 0.059 | 100% / 0.049 | 100% / 0.043 |
| qa-cases-page-size | 100% / 0.002 | 100% / 0.003 | 100% / 0.002 | 100% / 0.003 | 100% / 0.003 | 100% / 0.003 | 100% / 0.002 |
| qa-default-dedup-window | 100% / 0.003 | 100% / 0.002 | 100% / 0.002 | 100% / 0.003 | 100% / 0.002 | 100% / 0.002 | 100% / 0.002 |
| qa-filter-overview | 100% / 0.006 | 100% / 0.007 | 100% / 0.008 | 100% / 0.008 | 100% / 0.006 | 100% / 0.009 | 100% / 0.006 |
| qa-history-dedup-config | 100% / 0.003 | 100% / 0.003 | 100% / 0.002 | 100% / 0.002 | 100% / 0.002 | 100% / 0.002 | 100% / 0.003 |
| qa-signal-pipeline | 100% / 0.005 | 100% / 0.006 | 100% / 0.005 | 100% / 0.005 | 100% / 0.004 | 100% / 0.005 | 100% / 0.005 |
| qa-ui-entity-stats | 100% / 0.005 | 100% / 0.004 | 100% / 0.004 | 100% / 0.004 | 100% / 0.004 | 100% / 0.004 | 100% / 0.004 |
| refactor-merge-action | 100% / 0.011 | 100% / 0.010 | 100% / 0.009 | 100% / 0.015 | 100% / 0.011 | 100% / 0.011 | 100% / 0.013 |

## Run status per arm

| arm | ok | timeout | error | invalid |
|---|---|---|---|---|
| native | 40 | 0 | 0 | 0 |
| sobre-dev | 40 | 0 | 0 | 0 |
| sobre-dev-06 | 40 | 0 | 0 | 0 |
| sobre-dev-09 | 40 | 0 | 0 | 0 |
| sobre-dev-09b | 40 | 0 | 0 | 0 |
| sobre-hooks | 40 | 0 | 0 | 0 |
| sobre-keyonly | 40 | 0 | 0 | 0 |

## Not scored or flagged

| run | status | reason |
|---|---|---|
| audit-unprotected-endpoints__sobre-keyonly__r1 | ok, flagged | probe_inactive |
| audit-unprotected-endpoints__sobre-keyonly__r2 | ok, flagged | probe_inactive |
| change-filter-reason__sobre-dev-09__r1 | ok, flagged | network_command |
| change-filter-reason__sobre-dev-09b__r2 | ok, flagged | network_command |
| change-filter-reason__sobre-keyonly__r1 | ok, flagged | probe_inactive |
| change-filter-reason__sobre-keyonly__r2 | ok, flagged | probe_inactive |
| ci-red-regressions__sobre-keyonly__r1 | ok, flagged | probe_inactive |
| ci-red-regressions__sobre-keyonly__r2 | ok, flagged | probe_inactive |
| feature-signal-mute__sobre-dev__r2 | ok, flagged | network_command |
| feature-signal-mute__sobre-hooks__r2 | ok, flagged | network_command |
| feature-signal-mute__sobre-keyonly__r1 | ok, flagged | probe_inactive |
| feature-signal-mute__sobre-keyonly__r2 | ok, flagged | probe_inactive |
| fix-signal-stats-scope__sobre-keyonly__r1 | ok, flagged | probe_inactive |
| fix-signal-stats-scope__sobre-keyonly__r2 | ok, flagged | probe_inactive |
| fix-snooze-expired-filter__sobre-keyonly__r1 | ok, flagged | probe_inactive |
| fix-snooze-expired-filter__sobre-keyonly__r2 | ok, flagged | probe_inactive |
| history-dedup-commits__sobre-keyonly__r1 | ok, flagged | probe_inactive |
| history-dedup-commits__sobre-keyonly__r2 | ok, flagged | probe_inactive |
| log-dedup-regression__sobre-keyonly__r1 | ok, flagged | probe_inactive |
| log-dedup-regression__sobre-keyonly__r2 | ok, flagged | probe_inactive |
| log-reminders-stopped__sobre-keyonly__r1 | ok, flagged | probe_inactive |
| log-reminders-stopped__sobre-keyonly__r2 | ok, flagged | probe_inactive |
| mt-dedup-snooze-regressions__sobre-keyonly__r1 | ok, flagged | probe_inactive |
| mt-dedup-snooze-regressions__sobre-keyonly__r2 | ok, flagged | probe_inactive |
| mt-redaction-entities__sobre-keyonly__r1 | ok, flagged | probe_inactive |
| mt-redaction-entities__sobre-keyonly__r2 | ok, flagged | probe_inactive |
| mt-reminders-incident__sobre-keyonly__r1 | ok, flagged | probe_inactive |
| mt-reminders-incident__sobre-keyonly__r2 | ok, flagged | probe_inactive |
| mt-security-review__sobre-keyonly__r1 | ok, flagged | probe_inactive |
| mt-security-review__sobre-keyonly__r2 | ok, flagged | probe_inactive |
| qa-cases-page-size__sobre-keyonly__r1 | ok, flagged | probe_inactive |
| qa-cases-page-size__sobre-keyonly__r2 | ok, flagged | probe_inactive |
| qa-default-dedup-window__sobre-keyonly__r1 | ok, flagged | probe_inactive |
| qa-default-dedup-window__sobre-keyonly__r2 | ok, flagged | probe_inactive |
| qa-filter-overview__sobre-keyonly__r1 | ok, flagged | probe_inactive |
| qa-filter-overview__sobre-keyonly__r2 | ok, flagged | probe_inactive |
| qa-history-dedup-config__sobre-keyonly__r1 | ok, flagged | probe_inactive |
| qa-history-dedup-config__sobre-keyonly__r2 | ok, flagged | probe_inactive |
| qa-signal-pipeline__sobre-keyonly__r1 | ok, flagged | probe_inactive |
| qa-signal-pipeline__sobre-keyonly__r2 | ok, flagged | probe_inactive |
| qa-ui-entity-stats__sobre-keyonly__r1 | ok, flagged | probe_inactive |
| qa-ui-entity-stats__sobre-keyonly__r2 | ok, flagged | probe_inactive |
| refactor-merge-action__sobre-keyonly__r1 | ok, flagged | probe_inactive |
| refactor-merge-action__sobre-keyonly__r2 | ok, flagged | probe_inactive |
