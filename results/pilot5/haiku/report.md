# trust-me-bro report

48 scored runs (graded, or timed out or errored, which count as failures) out of 48. Bootstrap: 10000 resamples over tasks, seed 20261010. Non-inferiority margin: 5.0 percentage points of success. Cost: tokens x harness/prices.json (client estimate alongside).

## Per arm

| arm | runs | success | cost mean $ | cost median $ | client cost $ | input | output | cache read | cache write 5m | cache write 1h | turns | wall s | tool calls |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| native | 12 | 91.7% | 0.0612 | 0.0448 | 0.0640 | 1,223 | 33,657 | 2,439,592 | 91,286 | 0 | 51.8 | 516 | 46.2 |
| lean-ctx | 12 | 100.0% | 0.1003 | 0.0760 | 0.1010 | 1,565 | 39,794 | 3,356,468 | 122,631 | 0 | 73.6 | 569 | 68.1 |
| headroom | 12 | 100.0% | 0.0499 | 0.0455 | 0.0499 | 2,090 | 31,478 | 2,077,511 | 105,121 | 0 | 50.9 | 460 | 45.4 |
| rtk | 12 | 75.0% | 0.0826 | 0.0788 | 0.0861 | 1,327 | 43,248 | 3,676,676 | 102,453 | 0 | 73.9 | 693 | 68.4 |

## Paired with native (per-task means over reps)

| arm | tasks | Δ success (pp) | 95% CI | cost ratio (geo mean) | 95% CI | success verdict |
|---|---|---|---|---|---|---|
| lean-ctx | 4 | 8.3 | [0.0, 25.0] | 1.782 | [1.242, 2.582] | non-inferior |
| headroom | 4 | 8.3 | [0.0, 25.0] | 0.894 | [0.712, 1.124] | non-inferior |
| rtk | 4 | -16.7 | [-33.3, 0.0] | 1.480 | [0.997, 2.128] | inconclusive |

## Per task (success rate / mean cost $)

| task | native | lean-ctx | headroom | rtk |
|---|---|---|---|---|
| long-incident-then-dedup | 100% / 0.123 | 100% / 0.132 | 100% / 0.076 | 67% / 0.104 |
| long-security-then-redaction | 67% / 0.042 | 100% / 0.068 | 100% / 0.047 | 67% / 0.068 |
| mt-logs-case-cost | 100% / 0.044 | 100% / 0.133 | 100% / 0.036 | 100% / 0.106 |
| mt-reminders-incident | 100% / 0.035 | 100% / 0.069 | 100% / 0.040 | 67% / 0.051 |

## Run status per arm

| arm | ok | timeout | error | invalid |
|---|---|---|---|---|
| native | 12 | 0 | 0 | 0 |
| lean-ctx | 12 | 0 | 0 | 0 |
| headroom | 12 | 0 | 0 | 0 |
| rtk | 12 | 0 | 0 | 0 |

## Not scored or flagged

| run | status | reason |
|---|---|---|
| long-incident-then-dedup__rtk__r1 | ok, flagged | network_command |
| long-incident-then-dedup__rtk__r2 | ok, flagged | network_command |
| long-incident-then-dedup__rtk__r3 | ok, flagged | network_command |
| long-security-then-redaction__rtk__r1 | ok, flagged | network_command |
| long-security-then-redaction__rtk__r2 | ok, flagged | network_command |
| long-security-then-redaction__rtk__r3 | ok, flagged | network_command |
| mt-logs-case-cost__rtk__r1 | ok, flagged | network_command |
| mt-logs-case-cost__rtk__r2 | ok, flagged | network_command |
| mt-logs-case-cost__rtk__r3 | ok, flagged | network_command |
| mt-reminders-incident__rtk__r1 | ok, flagged | network_command |
| mt-reminders-incident__rtk__r2 | ok, flagged | network_command |
| mt-reminders-incident__rtk__r3 | ok, flagged | network_command |
