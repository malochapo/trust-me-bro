# Where to compact a long session

2026-10-13. Does it matter, for cost or for the answers, where a long session is compacted? Hosts compact at a fixed share of the window, from half of it (Gemini CLI) to about 97% (Claude Code), and research agents now learn when to compact. Before anyone builds a model to pick the moment, this test measures how much there is to gain on pilot 4's long sessions.

## The test

Pilot 4's part A tasks are seven-message conversations over two unrelated investigations, with a `/compact` between them, and a final recap that needs facts from both halves. `tasks5/` keeps every message and grader and moves the `/compact` (`tasks5/make.py`):

| Variant | `/compact` |
| --- | --- |
| `-c0` | none |
| `-c2` | after message 2, in the middle of the first investigation |
| `-c3` | after message 3, between the two investigations (pilot 4's own position, the reference) |
| `-c5` | after message 5, in the middle of the second investigation |

Claude Code alone (`native`), Haiku 5.5 at effort `medium`, pilot 4's fixture and settings, a 45-minute limit, interleaved runs, two at a time. All eight variants pass `tasks/validate.py`.

The plan was three repetitions of each, 24 runs. The first runs showed `long-incident-then-dedup-c5` at $0.53 and `-c0` at $0.30, against about $0.08 for the others, which would have put the test past its $2.45 cap. The bench was stopped there, and the other variants were run to three repetitions: that task's `-c0` and `-c5` have one run each. 20 runs, all valid and billed to the native key, $1.77.

## Results

| Task | `/compact` | Runs | Success | Facts in the recap (first half, second half) | Cost, cold start | Cost vs `-c3` | Largest prompt | Requests past 100K tokens |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `long-incident-then-dedup` | none | 1 | 1/1 | 6/6, 5/5 | $0.301 | 3.93 | 133,444 | 31 of 64 |
| | after message 2 | 3 | 3/3 | 18/18, 15/15 | $0.065 | 0.85 (0.68–1.05) | 86,081 | 0 |
| | after message 3 | 3 | 3/3 | 18/18, 15/15 | $0.077 | 1 | 88,643 | 0 |
| | after message 5 | 1 | 1/1 | 6/6, 5/5 | $0.535 | 6.98 | 167,697 | 49 of 83 |
| `long-security-then-redaction` | none | 3 | 3/3 | 24/24, 15/15 | $0.047 | 1.11 (0.98–1.26) | 83,761 | 0 |
| | after message 2 | 3 | 3/3 | 24/24, 15/15 | $0.045 | 1.05 (0.93–1.21) | 71,769 | 0 |
| | after message 3 | 3 | 3/3 | 24/24, 15/15 | $0.042 | 1 | 57,246 | 0 |
| | after message 5 | 3 | 3/3 | 24/24, 15/15 | $0.046 | 1.08 (0.99–1.18) | 68,119 | 0 |

Cost against `-c3`: ratio of mean cold-start costs, 95% bootstrap interval over runs (none for a single run, whose ratio only carries `-c3`'s spread). Hidden tests passed in every run. `harness/compaction_position.py` prints the full table, with the size of each compaction.

1. **Where it compacts did not change the answers.** Every run of every position succeeded, with every fact of both halves in the recap and no wrong line. One compaction in a seven-message session loses nothing here, wherever it falls.
2. **It changes the cost only through Haiku 5.5's price tier.** A request whose prompt passes 100,000 tokens pays five times the price for all its tokens. The log investigation reads megabytes of logs: compacted late or not at all, its prompt grew to 133,000 and 168,000 tokens, 31 of 64 and 49 of 83 requests went past the tier, and it cost 3.9 and 7.0 times as much. Priced without the tier, those two runs would have cost $0.095 and $0.146: most of the gap is the tier, the rest the longer prompt and, for the late compaction, a longer path (83 requests against 63).
3. **Below the tier, the position is noise.** The security review never reached 100,000 tokens, compacted or not, and its four positions cost within 11% of each other, inside their intervals. Compacting in the middle of the first investigation cost no more than between the two, and no fact was lost.

So on these sessions, a rule gets everything a model could: keep every request under the price tier. Compacting at a task boundary is a good place to do it, but not a better one than the middle of a task.

## Limits

- **Haiku only, two tasks, short sessions.** Seven messages and one compaction. Sonnet 5.5 has no long-prompt tier, so on it the cost side would be the smaller gap that remains without the tier. Sessions with several compactions, where the literature sees facts lost, are not tested.
- **Single runs** for the log investigation without compaction and with the late one: the ratio's size rests on one run each, though the tier makes the mechanism plain.
- **Quality at the ceiling.** Every run succeeded, so these tasks cannot show a position that costs answers; harder recaps might.
- **Claude Code's own auto-compaction is not used:** its default for Haiku 5.5 is about 967,000 tokens, so it never fires here. A window of 130,000 tokens (`autoCompactWindow`), which would trigger near 97,000, is the next test.

## Reproduce

```sh
python3 -I fixture/build.py --spec fixture/plants-pilot2.json --out build/pilot2
python3 -I fixture/gen_logs_pilot2.py build/pilot2
python3 -I tasks5/make.py
python3 -I tasks/validate.py --fixture build/pilot2/fixture.git --deps-venv "$BENCH_DEPS_VENV" --tasks-dir tasks5
python3 -I harness/bench.py --tasks 'tasks5/*/task.json' --arms native --reps 3 --jobs 2 --first-port 5436 \
    --stop-at-usd 2.45 --out results/compaction-position/haiku/raw \
    -- --model claude-haiku-5-5 --fixture build/pilot2/fixture.git --timeout-min 45
python3 -I harness/compaction_position.py
```
