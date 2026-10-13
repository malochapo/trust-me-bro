# trust-me-bro report

72 scored runs (graded, or timed out or errored, which count as failures) out of 72. Bootstrap: 10000 resamples over tasks, seed 20261010. Non-inferiority margin: 5.0 percentage points of success. Cost: tokens x harness/prices.json (client estimate alongside). Cold start: the same runs, each session priced as if it had started with a cold prompt cache (docs/cache-isolation.md).

## Per arm

| arm | runs | success | cost mean $ | cost median $ | cold-start cost mean $ | client cost $ | input | output | cache read | cache write 5m | cache write 1h | turns | wall s | tool calls |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| native | 21 | 100.0% | 0.0203 | 0.0036 | 0.0216 | 0.0203 | 720 | 13,288 | 862,163 | 39,990 | 0 | 23.0 | 191 | 20.2 |
| sobre-rc2-mcp | 15 | 93.3% | 0.0034 | 0.0034 | 0.0047 | 0.0034 | 11 | 1,568 | 100,292 | 12,965 | 0 | 5.4 | 15 | 4.4 |
| sobre-rc2-mcp-always | 21 | 95.2% | 0.0227 | 0.0060 | 0.0240 | 0.0235 | 721 | 12,613 | 1,006,953 | 47,645 | 0 | 22.6 | 175 | 19.9 |
| sobre-rc3-dense-always | 15 | 100.0% | 0.0044 | 0.0043 | 0.0057 | 0.0044 | 10 | 1,452 | 123,692 | 19,161 | 0 | 6.2 | 20 | 5.2 |

## Paired with native (per-task means over reps)

| arm | tasks | Δ success (pp) | 95% CI | cost ratio (geo mean) | 95% CI | cold-start cost ratio | 95% CI | success verdict |
|---|---|---|---|---|---|---|---|---|
| sobre-rc2-mcp | 5 | -6.7 | [-20.0, 0.0] | 0.980 | [0.880, 1.106] | 0.985 | [0.910, 1.075] | inconclusive |
| sobre-rc2-mcp-always | 7 | -4.8 | [-14.3, 0.0] | 1.313 | [1.108, 1.550] | 1.242 | [1.130, 1.357] | inconclusive |
| sobre-rc3-dense-always | 5 | 0.0 | [0.0, 0.0] | 1.236 | [1.001, 1.526] | 1.200 | [1.088, 1.320] | non-inferior |

## Per task (success rate / mean cost $)

| task | native | sobre-rc2-mcp | sobre-rc2-mcp-always | sobre-rc3-dense-always |
|---|---|---|---|---|
| long-incident-then-dedup | 100% / 0.079 | - | 100% / 0.086 | - |
| long-security-then-redaction | 100% / 0.046 | - | 67% / 0.047 | - |
| ss-call-invite-choice | 100% / 0.003 | 67% / 0.004 | 100% / 0.004 | 100% / 0.005 |
| ss-latecomer-briefing | 100% / 0.003 | 100% / 0.004 | 100% / 0.006 | 100% / 0.006 |
| ss-oncall-turn-tally | 100% / 0.004 | 100% / 0.003 | 100% / 0.004 | 100% / 0.005 |
| ss-signal-post-redraw | 100% / 0.004 | 100% / 0.003 | 100% / 0.006 | 100% / 0.004 |
| ss-thread-case-bring-in | 100% / 0.004 | 100% / 0.003 | 100% / 0.006 | 100% / 0.003 |

## Run status per arm

| arm | ok | timeout | error | invalid |
|---|---|---|---|---|
| native | 21 | 0 | 0 | 0 |
| sobre-rc2-mcp | 15 | 0 | 0 | 0 |
| sobre-rc2-mcp-always | 21 | 0 | 0 | 0 |
| sobre-rc3-dense-always | 15 | 0 | 0 | 0 |

## Not scored or flagged

None.
