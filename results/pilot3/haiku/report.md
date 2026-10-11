# sobre-bench report

280 scored runs (graded, or timed out or errored, which count as failures) out of 280. Bootstrap: 10000 resamples over tasks, seed 20261010. Non-inferiority margin: 5.0 percentage points of success. Cost: tokens x harness/prices.json (client estimate alongside).

## Per arm

| arm | runs | success | cost mean $ | cost median $ | client cost $ | input | output | cache read | cache write 5m | cache write 1h | turns | wall s | tool calls |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| native | 40 | 100.0% | 0.0116 | 0.0063 | 0.0116 | 26 | 7,616 | 449,349 | 26,183 | 0 | 14.9 | 89 | 13.3 |
| sobre-dev | 40 | 100.0% | 0.0135 | 0.0069 | 0.0135 | 30 | 8,343 | 564,420 | 29,145 | 0 | 16.8 | 113 | 15.2 |
| sobre-dev-06 | 40 | 95.0% | 0.0145 | 0.0075 | 0.0144 | 28 | 8,000 | 529,454 | 28,143 | 0 | 16.0 | 97 | 14.4 |
| sobre-dev-09 | 40 | 100.0% | 0.0133 | 0.0072 | 0.0133 | 29 | 8,458 | 547,713 | 28,828 | 0 | 16.4 | 111 | 14.8 |
| sobre-dev-09b | 40 | 100.0% | 0.0133 | 0.0066 | 0.0134 | 28 | 8,250 | 536,210 | 27,975 | 0 | 16.4 | 108 | 14.8 |
| sobre-hooks | 40 | 97.5% | 0.0133 | 0.0081 | 0.0133 | 30 | 8,364 | 548,202 | 28,990 | 0 | 16.6 | 114 | 15.1 |
| sobre-keyonly | 40 | 100.0% | 0.0126 | 0.0075 | 0.0126 | 27 | 8,131 | 497,449 | 28,120 | 0 | 15.9 | 86 | 14.3 |

## Paired with native (per-task means over reps)

| arm | tasks | Δ success (pp) | 95% CI | cost ratio (geo mean) | 95% CI | success verdict |
|---|---|---|---|---|---|---|
| sobre-dev | 20 | 0.0 | [0.0, 0.0] | 1.096 | [1.018, 1.188] | non-inferior |
| sobre-dev-06 | 20 | -5.0 | [-12.5, 0.0] | 1.050 | [0.961, 1.168] | inconclusive |
| sobre-dev-09 | 20 | 0.0 | [0.0, 0.0] | 1.070 | [1.002, 1.141] | non-inferior |
| sobre-dev-09b | 20 | 0.0 | [0.0, 0.0] | 1.047 | [0.985, 1.118] | non-inferior |
| sobre-hooks | 20 | -2.5 | [-7.5, 0.0] | 1.111 | [1.019, 1.216] | inconclusive |
| sobre-keyonly | 20 | 0.0 | [0.0, 0.0] | 1.033 | [0.960, 1.124] | non-inferior |

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
| mt-dedup-snooze-regressions | 100% / 0.023 | 100% / 0.028 | 100% / 0.027 | 100% / 0.030 | 100% / 0.030 | 100% / 0.031 | 100% / 0.039 |
| mt-redaction-entities | 100% / 0.023 | 100% / 0.024 | 100% / 0.025 | 100% / 0.022 | 100% / 0.022 | 100% / 0.023 | 100% / 0.023 |
| mt-reminders-incident | 100% / 0.038 | 100% / 0.045 | 100% / 0.084 | 100% / 0.050 | 100% / 0.039 | 100% / 0.038 | 100% / 0.034 |
| mt-security-review | 100% / 0.018 | 100% / 0.017 | 50% / 0.018 | 100% / 0.017 | 100% / 0.021 | 100% / 0.018 | 100% / 0.016 |
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
