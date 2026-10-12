# trust-me-bro report

176 scored runs (graded, or timed out or errored, which count as failures) out of 176. Bootstrap: 10000 resamples over tasks, seed 20261010. Non-inferiority margin: 5.0 percentage points of success. Cost: tokens x harness/prices.json (client estimate alongside). Cold start: the same runs, each session priced as if it had started with a cold prompt cache (docs/cache-isolation.md).

## Per arm

| arm | runs | success | cost mean $ | cost median $ | cold-start cost mean $ | client cost $ | input | output | cache read | cache write 5m | cache write 1h | turns | wall s | tool calls |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| native | 47 | 97.9% | 0.0317 | 0.0327 | 0.0333 | 0.0318 | 346 | 18,992 | 1,322,060 | 61,771 | 0 | 31.9 | 256 | 28.9 |
| native-told | 12 | 100.0% | 0.0272 | 0.0264 | 0.0300 | 0.0272 | 58 | 18,713 | 932,417 | 68,163 | 0 | 35.4 | 282 | 32.8 |
| sobre-rc2 | 16 | 100.0% | 0.0562 | 0.0449 | 0.0575 | 0.0563 | 946 | 31,561 | 2,393,087 | 87,260 | 0 | 51.9 | 505 | 46.4 |
| sobre-rc2-mcp | 33 | 93.9% | 0.0217 | 0.0202 | 0.0235 | 0.0222 | 470 | 14,823 | 819,887 | 48,154 | 0 | 26.4 | 188 | 23.7 |
| sobre-rc2-mcp-told | 27 | 100.0% | 0.0121 | 0.0053 | 0.0141 | 0.0121 | 29 | 7,764 | 412,520 | 32,736 | 0 | 18.6 | 82 | 16.9 |
| sobre-rc3-dense | 2 | 100.0% | 0.0036 | 0.0036 | 0.0049 | 0.0036 | 13 | 1,728 | 120,382 | 12,162 | 0 | 6.5 | 15 | 5.5 |
| sobre-rc3-dense-told | 15 | 100.0% | 0.0044 | 0.0045 | 0.0057 | 0.0044 | 14 | 2,073 | 140,397 | 15,572 | 0 | 8.5 | 27 | 7.5 |
| sobre-dev-fold2 | 14 | 85.7% | 0.0375 | 0.0350 | 0.0388 | 0.0375 | 64 | 24,241 | 1,717,570 | 65,716 | 0 | 38.6 | 363 | 34.6 |
| sobre-dev-fold3 | 10 | 100.0% | 0.0446 | 0.0452 | 0.0459 | 0.0446 | 73 | 26,750 | 2,181,395 | 75,118 | 0 | 44.3 | 435 | 40.2 |

## Paired with native (per-task means over reps)

| arm | tasks | Δ success (pp) | 95% CI | cost ratio (geo mean) | 95% CI | cold-start cost ratio | 95% CI | success verdict |
|---|---|---|---|---|---|---|---|---|
| native-told | 4 | 0.0 | [0.0, 0.0] | 0.904 | [0.672, 1.186] | 0.910 | [0.694, 1.166] | non-inferior |
| sobre-rc2 | 4 | 8.3 | [0.0, 25.0] | 1.007 | [0.869, 1.157] | 1.007 | [0.872, 1.153] | non-inferior |
| sobre-rc2-mcp | 11 | -3.0 | [-12.1, 6.1] | 0.970 | [0.836, 1.084] | 0.967 | [0.847, 1.064] | inconclusive |
| sobre-rc2-mcp-told | 9 | 0.0 | [0.0, 0.0] | 0.992 | [0.770, 1.216] | 0.972 | [0.782, 1.155] | non-inferior |
| sobre-rc3-dense | 2 | 0.0 | [0.0, 0.0] | 1.099 | [1.094, 1.105] | 1.071 | [1.067, 1.076] | non-inferior |
| sobre-rc3-dense-told | 5 | 0.0 | [0.0, 0.0] | 1.305 | [1.209, 1.386] | 1.220 | [1.154, 1.276] | non-inferior |
| sobre-dev-fold2 | 2 | -10.0 | [-20.0, 0.0] | 0.670 | [0.550, 0.816] | 0.678 | [0.560, 0.821] | inconclusive |
| sobre-dev-fold3 | 2 | 0.0 | [0.0, 0.0] | 0.851 | [0.797, 0.909] | 0.855 | [0.802, 0.911] | non-inferior |

## Per task (success rate / mean cost $)

| task | native | native-told | sobre-rc2 | sobre-rc2-mcp | sobre-rc2-mcp-told | sobre-rc3-dense | sobre-rc3-dense-told | sobre-dev-fold2 | sobre-dev-fold3 |
|---|---|---|---|---|---|---|---|---|---|
| long-incident-then-dedup | 100% / 0.072 | - | 100% / 0.073 | 67% / 0.072 | - | - | - | - | - |
| long-security-then-redaction | 67% / 0.046 | - | 100% / 0.046 | 100% / 0.049 | - | - | - | - | - |
| mt-logs-case-cost | 100% / 0.049 | - | 100% / 0.060 | - | - | - | - | 80% / 0.040 | 100% / 0.045 |
| mt-reminders-incident | 100% / 0.055 | - | 100% / 0.046 | - | - | - | - | 100% / 0.030 | 100% / 0.044 |
| ss-call-invite-choice | 100% / 0.003 | - | - | 100% / 0.003 | 100% / 0.004 | 100% / 0.003 | 100% / 0.005 | - | - |
| ss-latecomer-briefing | 100% / 0.003 | - | - | 100% / 0.004 | 100% / 0.004 | - | 100% / 0.004 | - | - |
| ss-oncall-turn-tally | 100% / 0.004 | - | - | 100% / 0.004 | 100% / 0.005 | - | 100% / 0.004 | - | - |
| ss-signal-post-redraw | 100% / 0.003 | - | - | 100% / 0.003 | 100% / 0.004 | 100% / 0.004 | 100% / 0.004 | - | - |
| ss-thread-case-bring-in | 100% / 0.003 | - | - | 100% / 0.004 | 100% / 0.005 | - | 100% / 0.004 | - | - |
| xs-dedup-next-day | 100% / 0.024 | 100% / 0.029 | - | 100% / 0.025 | 100% / 0.022 | - | - | - | - |
| xs-dedup-saved | 100% / 0.026 | 100% / 0.030 | - | 67% / 0.028 | 100% / 0.024 | - | - | - | - |
| xs-reminders-next-day | 100% / 0.043 | 100% / 0.024 | - | 100% / 0.023 | 100% / 0.019 | - | - | - | - |
| xs-reminders-saved | 100% / 0.031 | 100% / 0.026 | - | 100% / 0.024 | 100% / 0.022 | - | - | - | - |

## Run status per arm

| arm | ok | timeout | error | invalid |
|---|---|---|---|---|
| native | 47 | 0 | 0 | 0 |
| native-told | 12 | 0 | 0 | 0 |
| sobre-rc2 | 16 | 0 | 0 | 0 |
| sobre-rc2-mcp | 33 | 0 | 0 | 0 |
| sobre-rc2-mcp-told | 27 | 0 | 0 | 0 |
| sobre-rc3-dense | 2 | 0 | 0 | 0 |
| sobre-rc3-dense-told | 15 | 0 | 0 | 0 |
| sobre-dev-fold2 | 14 | 0 | 0 | 0 |
| sobre-dev-fold3 | 10 | 0 | 0 | 0 |

## Not scored or flagged

| run | status | reason |
|---|---|---|
| xs-dedup-next-day__native-told__r1 | ok, flagged | probe_inactive |
| xs-dedup-next-day__native-told__r2 | ok, flagged | probe_inactive |
| xs-dedup-next-day__native-told__r3 | ok, flagged | probe_inactive |
| xs-dedup-saved__native-told__r1 | ok, flagged | probe_inactive |
| xs-dedup-saved__native-told__r2 | ok, flagged | probe_inactive |
| xs-dedup-saved__native-told__r3 | ok, flagged | probe_inactive |
| xs-reminders-next-day__native-told__r1 | ok, flagged | probe_inactive |
| xs-reminders-next-day__native-told__r2 | ok, flagged | probe_inactive |
| xs-reminders-next-day__native-told__r3 | ok, flagged | probe_inactive |
| xs-reminders-saved__native-told__r1 | ok, flagged | probe_inactive |
| xs-reminders-saved__native-told__r2 | ok, flagged | probe_inactive |
| xs-reminders-saved__native-told__r3 | ok, flagged | probe_inactive |
