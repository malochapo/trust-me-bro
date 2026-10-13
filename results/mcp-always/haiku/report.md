# trust-me-bro report

60 scored runs (graded, or timed out or errored, which count as failures) out of 60. Bootstrap: 10000 resamples over tasks, seed 20261010. Non-inferiority margin: 5.0 percentage points of success. Cost: tokens x harness/prices.json (client estimate alongside). Cold start: the same runs, each session priced as if it had started with a cold prompt cache (docs/cache-isolation.md).

## Per arm

| arm | runs | success | cost mean $ | cost median $ | cold-start cost mean $ | client cost $ | input | output | cache read | cache write 5m | cache write 1h | turns | wall s | tool calls |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| native | 15 | 100.0% | 0.0035 | 0.0035 | 0.0048 | 0.0035 | 12 | 1,545 | 107,641 | 13,124 | 0 | 5.8 | 13 | 4.8 |
| sobre-rc2-mcp | 15 | 93.3% | 0.0034 | 0.0034 | 0.0047 | 0.0034 | 11 | 1,568 | 100,292 | 12,965 | 0 | 5.4 | 15 | 4.4 |
| sobre-rc2-mcp-always | 15 | 100.0% | 0.0051 | 0.0051 | 0.0063 | 0.0051 | 12 | 1,681 | 144,906 | 22,220 | 0 | 6.3 | 19 | 5.3 |
| sobre-rc3-dense-always | 15 | 100.0% | 0.0044 | 0.0043 | 0.0057 | 0.0044 | 10 | 1,452 | 123,692 | 19,161 | 0 | 6.2 | 20 | 5.2 |

## Paired with native (per-task means over reps)

| arm | tasks | Δ success (pp) | 95% CI | cost ratio (geo mean) | 95% CI | cold-start cost ratio | 95% CI | success verdict |
|---|---|---|---|---|---|---|---|---|
| sobre-rc2-mcp | 5 | -6.7 | [-20.0, 0.0] | 0.980 | [0.880, 1.106] | 0.985 | [0.910, 1.075] | inconclusive |
| sobre-rc2-mcp-always | 5 | 0.0 | [0.0, 0.0] | 1.430 | [1.166, 1.670] | 1.322 | [1.215, 1.408] | non-inferior |
| sobre-rc3-dense-always | 5 | 0.0 | [0.0, 0.0] | 1.236 | [1.001, 1.526] | 1.200 | [1.088, 1.320] | non-inferior |

## Per task (success rate / mean cost $)

| task | native | sobre-rc2-mcp | sobre-rc2-mcp-always | sobre-rc3-dense-always |
|---|---|---|---|---|
| ss-call-invite-choice | 100% / 0.003 | 67% / 0.004 | 100% / 0.004 | 100% / 0.005 |
| ss-latecomer-briefing | 100% / 0.003 | 100% / 0.004 | 100% / 0.006 | 100% / 0.006 |
| ss-oncall-turn-tally | 100% / 0.004 | 100% / 0.003 | 100% / 0.004 | 100% / 0.005 |
| ss-signal-post-redraw | 100% / 0.004 | 100% / 0.003 | 100% / 0.006 | 100% / 0.004 |
| ss-thread-case-bring-in | 100% / 0.004 | 100% / 0.003 | 100% / 0.006 | 100% / 0.003 |

## Run status per arm

| arm | ok | timeout | error | invalid |
|---|---|---|---|---|
| native | 15 | 0 | 0 | 0 |
| sobre-rc2-mcp | 15 | 0 | 0 | 0 |
| sobre-rc2-mcp-always | 15 | 0 | 0 | 0 |
| sobre-rc3-dense-always | 15 | 0 | 0 | 0 |

## Not scored or flagged

None.
