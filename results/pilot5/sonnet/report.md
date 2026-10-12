# trust-me-bro report

24 scored runs (graded, or timed out or errored, which count as failures) out of 24. Bootstrap: 10000 resamples over tasks, seed 20261010. Non-inferiority margin: 5.0 percentage points of success. Cost: tokens x harness/prices.json (client estimate alongside). Cold start: the same runs, each session priced as if it had started with a cold prompt cache (docs/cache-isolation.md).

## Per arm

| arm | runs | success | cost mean $ | cost median $ | cold-start cost mean $ | client cost $ | input | output | cache read | cache write 5m | cache write 1h | turns | wall s | tool calls |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| native | 6 | 100.0% | 0.3643 | 0.3673 | 0.3909 | 0.3643 | 1,131 | 13,798 | 966,294 | 50,964 | 0 | 30.0 | 251 | 24.5 |
| lean-ctx | 6 | 100.0% | 0.4597 | 0.4401 | 0.4721 | 0.4597 | 1,154 | 15,128 | 1,282,978 | 71,113 | 0 | 39.2 | 262 | 33.7 |
| headroom | 6 | 100.0% | 0.4034 | 0.4166 | 0.4197 | 0.4034 | 1,144 | 15,023 | 1,064,995 | 57,761 | 0 | 32.5 | 291 | 27.0 |
| rtk | 6 | 100.0% | 0.4375 | 0.4425 | 0.4641 | 0.4375 | 1,256 | 16,352 | 1,282,614 | 57,275 | 0 | 37.8 | 312 | 32.3 |

## Paired with native (per-task means over reps)

| arm | tasks | Δ success (pp) | 95% CI | cost ratio (geo mean) | 95% CI | cold-start cost ratio | 95% CI | success verdict |
|---|---|---|---|---|---|---|---|---|
| lean-ctx | 2 | 0.0 | [0.0, 0.0] | 1.231 | [1.025, 1.479] | 1.180 | [0.985, 1.413] | non-inferior |
| headroom | 2 | 0.0 | [0.0, 0.0] | 1.108 | [1.053, 1.167] | 1.074 | [1.024, 1.127] | non-inferior |
| rtk | 2 | 0.0 | [0.0, 0.0] | 1.192 | [1.094, 1.299] | 1.180 | [1.087, 1.280] | non-inferior |

## Per task (success rate / mean cost $)

| task | native | lean-ctx | headroom | rtk |
|---|---|---|---|---|
| long-security-then-redaction | 100% / 0.380 | 100% / 0.562 | 100% / 0.400 | 100% / 0.493 |
| mt-logs-case-cost | 100% / 0.349 | 100% / 0.358 | 100% / 0.407 | 100% / 0.382 |

## Run status per arm

| arm | ok | timeout | error | invalid |
|---|---|---|---|---|
| native | 6 | 0 | 0 | 0 |
| lean-ctx | 6 | 0 | 0 | 0 |
| headroom | 6 | 0 | 0 | 0 |
| rtk | 6 | 0 | 0 | 0 |

## Not scored or flagged

| run | status | reason |
|---|---|---|
| long-security-then-redaction__rtk__r1 | ok, flagged | network_command |
