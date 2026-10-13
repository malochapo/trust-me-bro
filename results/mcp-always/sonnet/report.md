# trust-me-bro report

30 scored runs (graded, or timed out or errored, which count as failures) out of 30. Bootstrap: 10000 resamples over tasks, seed 20261010. Non-inferiority margin: 5.0 percentage points of success. Cost: tokens x harness/prices.json (client estimate alongside). Cold start: the same runs, each session priced as if it had started with a cold prompt cache (docs/cache-isolation.md).

## Per arm

| arm | runs | success | cost mean $ | cost median $ | cold-start cost mean $ | client cost $ | input | output | cache read | cache write 5m | cache write 1h | turns | wall s | tool calls |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| native | 15 | 100.0% | 0.0374 | 0.0384 | 0.0641 | 0.0374 | 8 | 849 | 67,350 | 8,864 | 0 | 4.3 | 11 | 3.3 |
| sobre-rc2-mcp-always | 15 | 100.0% | 0.0494 | 0.0482 | 0.0903 | 0.0494 | 9 | 1,109 | 108,491 | 10,980 | 0 | 5.7 | 14 | 4.7 |

## Paired with native (per-task means over reps)

| arm | tasks | Δ success (pp) | 95% CI | cost ratio (geo mean) | 95% CI | cold-start cost ratio | 95% CI | success verdict |
|---|---|---|---|---|---|---|---|---|
| sobre-rc2-mcp-always | 5 | 0.0 | [0.0, 0.0] | 1.323 | [1.170, 1.456] | 1.405 | [1.312, 1.503] | non-inferior |

## Per task (success rate / mean cost $)

| task | native | sobre-rc2-mcp-always |
|---|---|---|
| ss-call-invite-choice | 100% / 0.038 | 100% / 0.047 |
| ss-latecomer-briefing | 100% / 0.043 | 100% / 0.046 |
| ss-oncall-turn-tally | 100% / 0.041 | 100% / 0.060 |
| ss-signal-post-redraw | 100% / 0.031 | 100% / 0.045 |
| ss-thread-case-bring-in | 100% / 0.034 | 100% / 0.050 |

## Run status per arm

| arm | ok | timeout | error | invalid |
|---|---|---|---|---|
| native | 15 | 0 | 0 | 0 |
| sobre-rc2-mcp-always | 15 | 0 | 0 | 0 |

## Not scored or flagged

None.
