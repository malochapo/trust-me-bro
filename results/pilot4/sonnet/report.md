# trust-me-bro report

150 scored runs (graded, or timed out or errored, which count as failures) out of 150. Bootstrap: 10000 resamples over tasks, seed 20261010. Non-inferiority margin: 5.0 percentage points of success. Cost: tokens x harness/prices.json (client estimate alongside). Cold start: the same runs, each session priced as if it had started with a cold prompt cache (docs/cache-isolation.md).

## Per arm

| arm | runs | success | cost mean $ | cost median $ | cold-start cost mean $ | client cost $ | input | output | cache read | cache write 5m | cache write 1h | turns | wall s | tool calls |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| native | 43 | 100.0% | 0.2125 | 0.2080 | 0.2478 | 0.2125 | 354 | 7,584 | 507,264 | 34,076 | 0 | 17.6 | 164 | 14.6 |
| native-told | 12 | 100.0% | 0.2136 | 0.2055 | 0.2703 | 0.2136 | 36 | 7,416 | 423,904 | 38,780 | 0 | 19.8 | 129 | 17.2 |
| sobre-rc2 | 16 | 100.0% | 0.3333 | 0.2833 | 0.3599 | 0.3333 | 891 | 12,908 | 840,647 | 47,345 | 0 | 27.3 | 281 | 22.2 |
| sobre-rc2-mcp | 33 | 100.0% | 0.1820 | 0.1635 | 0.2200 | 0.1820 | 446 | 6,774 | 413,159 | 28,816 | 0 | 16.3 | 156 | 13.7 |
| sobre-rc2-mcp-told | 27 | 100.0% | 0.1329 | 0.0504 | 0.1729 | 0.1329 | 24 | 4,281 | 286,653 | 24,549 | 0 | 13.6 | 100 | 11.9 |
| sobre-rc3-dense-told | 5 | 100.0% | 0.0397 | 0.0398 | 0.0663 | 0.0397 | 9 | 860 | 76,328 | 9,370 | 0 | 4.6 | 13 | 3.6 |
| sobre-dev-fold2 | 4 | 100.0% | 0.2870 | 0.2857 | 0.3136 | 0.2870 | 44 | 10,321 | 798,616 | 41,531 | 0 | 24.0 | 241 | 20.0 |
| sobre-dev-fold3 | 10 | 100.0% | 0.3138 | 0.3046 | 0.3404 | 0.3138 | 45 | 10,731 | 917,909 | 45,835 | 0 | 24.6 | 267 | 20.6 |

## Paired with native (per-task means over reps)

| arm | tasks | Δ success (pp) | 95% CI | cost ratio (geo mean) | 95% CI | cold-start cost ratio | 95% CI | success verdict |
|---|---|---|---|---|---|---|---|---|
| native-told | 4 | 0.0 | [0.0, 0.0] | 0.993 | [0.866, 1.138] | 0.992 | [0.888, 1.109] | non-inferior |
| sobre-rc2 | 4 | 0.0 | [0.0, 0.0] | 0.907 | [0.833, 0.987] | 0.913 | [0.843, 0.988] | non-inferior |
| sobre-rc2-mcp | 11 | 0.0 | [0.0, 0.0] | 0.991 | [0.925, 1.059] | 0.990 | [0.940, 1.041] | non-inferior |
| sobre-rc2-mcp-told | 9 | 0.0 | [0.0, 0.0] | 1.102 | [1.032, 1.174] | 1.073 | [1.023, 1.129] | non-inferior |
| sobre-rc3-dense-told | 5 | 0.0 | [0.0, 0.0] | 1.084 | [0.974, 1.260] | 1.047 | [0.984, 1.140] | non-inferior |
| sobre-dev-fold2 | 1 | 0.0 | [0.0, 0.0] | 0.840 | [0.840, 0.840] | 0.852 | [0.852, 0.852] | non-inferior |
| sobre-dev-fold3 | 2 | 0.0 | [0.0, 0.0] | 1.098 | [0.982, 1.228] | 1.088 | [0.983, 1.204] | non-inferior |

## Per task (success rate / mean cost $)

| task | native | native-told | sobre-rc2 | sobre-rc2-mcp | sobre-rc2-mcp-told | sobre-rc3-dense-told | sobre-dev-fold2 | sobre-dev-fold3 |
|---|---|---|---|---|---|---|---|---|
| long-incident-then-dedup | 100% / 0.632 | - | 100% / 0.540 | 100% / 0.622 | - | - | - | - |
| long-security-then-redaction | 100% / 0.387 | - | 100% / 0.379 | 100% / 0.375 | - | - | - | - |
| mt-logs-case-cost | 100% / 0.342 | - | 100% / 0.277 | - | - | - | 100% / 0.287 | 100% / 0.335 |
| mt-reminders-incident | 100% / 0.229 | - | 100% / 0.228 | - | - | - | - | 100% / 0.281 |
| ss-call-invite-choice | 100% / 0.035 | - | - | 100% / 0.040 | 100% / 0.037 | 100% / 0.037 | - | - |
| ss-latecomer-briefing | 100% / 0.043 | - | - | 100% / 0.042 | 100% / 0.038 | 100% / 0.040 | - | - |
| ss-oncall-turn-tally | 100% / 0.040 | - | - | 100% / 0.043 | 100% / 0.046 | 100% / 0.041 | - | - |
| ss-signal-post-redraw | 100% / 0.029 | - | - | 100% / 0.030 | 100% / 0.030 | 100% / 0.042 | - | - |
| ss-thread-case-bring-in | 100% / 0.037 | - | - | 100% / 0.037 | 100% / 0.042 | 100% / 0.038 | - | - |
| xs-dedup-next-day | 100% / 0.206 | 100% / 0.235 | - | 100% / 0.250 | 100% / 0.243 | - | - | - |
| xs-dedup-saved | 100% / 0.207 | 100% / 0.172 | - | 100% / 0.180 | 100% / 0.276 | - | - | - |
| xs-reminders-next-day | 100% / 0.214 | 100% / 0.243 | - | 100% / 0.208 | 100% / 0.226 | - | - | - |
| xs-reminders-saved | 100% / 0.226 | 100% / 0.205 | - | 100% / 0.176 | 100% / 0.258 | - | - | - |

## Run status per arm

| arm | ok | timeout | error | invalid |
|---|---|---|---|---|
| native | 43 | 0 | 0 | 0 |
| native-told | 12 | 0 | 0 | 0 |
| sobre-rc2 | 16 | 0 | 0 | 0 |
| sobre-rc2-mcp | 33 | 0 | 0 | 0 |
| sobre-rc2-mcp-told | 27 | 0 | 0 | 0 |
| sobre-rc3-dense-told | 5 | 0 | 0 | 0 |
| sobre-dev-fold2 | 4 | 0 | 0 | 0 |
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
