# Pilot 2: harder tasks

Run on 2026-10-10. The aggregate numbers are in [results/pilot2/report.md](../results/pilot2/report.md), and every run's raw data is in `results/pilot2/raw/`.

Pilot 1 showed that its tasks were too easy to separate the arms: all 100 runs succeeded. Its runs were short, 5 to 9 turns and about 30 s each, so there was little context to compress, and each tool's fixed overhead decided its cost. Pilot 2 is a second pilot, not the full benchmark. It checks that longer, harder tasks are feasible, measure something, and fit the budget before phase 2 is frozen.

## What changes

- **A fixture of its own.** `fixture/plants-pilot2.json` keeps the 8 pilot 1 plants and adds 5 more, which touch files no pilot 1 plant touches. Build it with `python3 -I fixture/build.py --spec fixture/plants-pilot2.json --out build/pilot2`. It ships with three regressions that make CI red: plants `q1` to `q3`, in the last commits before HEAD.
- **Tasks that need much more context.** They mean repeated full test-suite runs, two ~600-line view modules read end to end, a 5,000-commit history, megabytes of logs from two services, and changes across the backend, a migration and the UI.
- **Graders that editing tests cannot fool.** `ci-red-regressions` restores the original tests (`git checkout {FIXTURE_HEAD} -- tests`) before running the whole suite.
- **Upstream commits by name.** The fixture build now records each replayed upstream commit's new id, so a task can refer to it as `{plant:<upstream sha>}`.

## Tasks (`tasks2/`)

| Task | Family | Grader | What makes it hard |
| --- | --- | --- | --- |
| `ci-red-regressions` | bug fix | whole suite, original tests | Three unrelated regressions in three packages, found through full pytest runs |
| `feature-signal-mute` | cross-layer | hidden tests + static checks | Enum, model, schema, filter logic, migration, table, store and dialog |
| `refactor-merge-action` | refactor | hidden tests + static checks | A rename across backend, UI and tests, plus a data migration on two tables |
| `log-reminders-stopped` | log diagnosis | facts | Several MB of scheduler and API logs from two services; the cause is a weekday off-by-one in a refactor |
| `history-dedup-commits` | history | facts, precision included | Every commit that changed snooze or deduplication since a date, without the neighbors |
| `audit-unprotected-endpoints` | code QA | facts, precision included | Every mutating route of two view modules, checked for a permission dependency |

## Arms and budget

The same five arms as pilot 1. When sobre's overhead cuts are ready, a sixth arm adds a development build, `sobre-dev`, measured against `sobre` 0.1.0-rc.1. The run settings stay those of pilot 1: Sonnet 5.5 at effort medium, a $3 cap and a 25-minute timeout per run.

The budget is about $30 per repetition for 30 runs, plus about $6 for `sobre-dev`. That leaves room for two repetitions within the remaining API credit.

## Run

```sh
python3 -I fixture/build.py --spec fixture/plants-pilot2.json --out build/pilot2
python3 -I fixture/gen_logs_pilot2.py build/pilot2
python3 -I tasks/validate.py --fixture build/pilot2/fixture.git --deps-venv "$BENCH_DEPS_VENV" --tasks-dir tasks2
python3 -I harness/leakage.py --tasks 'tasks2/*/task.json' --plants build/pilot2/plants.json --out results/pilot2/leakage
# phase 0 result: the 3 fact tasks were each answered 0/3 times without the code
python3 -I harness/bench.py --tasks 'tasks2/*/task.json' --reps 1 --out results/pilot2/raw --stop-at-usd 40 \
    -- --fixture build/pilot2/fixture.git
python3 -I harness/report.py --raw results/pilot2/raw --out results/pilot2
```

## Results

The pilot ran 6 tasks × 7 arms × 2 repetitions, 84 runs in all. Every run was valid and every run succeeded. The seven arms are the five of pilot 1 and sobre's two development arms ([sobre-dev.md](sobre-dev.md)).

| Arm | Mean cost per run | Cost vs native, geometric mean of per-task ratios | 95% CI | Turns |
| --- | --- | --- | --- | --- |
| native | $0.077 | 1 | | 7.0 |
| sobre 0.1.0-rc.1 | $0.088 | 1.08 | 0.96–1.23 | 7.8 |
| rtk 0.51.0 | $0.085 | 1.10 | 0.91–1.44 | 8.2 |
| Headroom 0.40.0 | $0.100 | 1.30 | 1.22–1.40 | 7.0 |
| lean-ctx 3.11.2 | $0.141 | 1.81 | 1.52–2.11 | 11.0 |
| `sobre-dev` | $0.079 | 1.01 | 0.92–1.10 | 6.9 |
| `sobre-hooks` | $0.074 | 0.97 | 0.83–1.09 | 6.7 |

Costs use the corrected price of Sonnet 5.5 cache hits ($0.10 per million tokens; PROTOCOL.md changelog).

**Spend:** $7.72 computed for the 84 runs. Across both pilots and every arm, the computed spend is $16.54, plus about $1 for the judge and the leakage checks.

**Flag:** one rtk run (`ci-red-regressions`, repetition 1) ran a network command.

## What pilot 2 taught

1. **Harder tasks did not separate the arms on success either.** Sonnet 5.5 solved all 84 runs, the three-regression CI task and the cross-layer feature included. Runs cost 40% more than in pilot 1 ($0.077 against $0.055 for native), with more turns. They were still not long enough to strain the context.
2. **The agent keeps its outputs small by itself.** Even with megabytes of logs and full test-suite runs, it piped into `head`, `tail` and `cut`, and counted with `grep -c`. Tool results made up about 24% of native's cost. Logs, history and test output, the part a tool could compress without touching source code, made up about 12%.
3. **The noise is wide with 6 tasks.** One cheap rtk run on the log task moves rtk's interval from 0.68 to 1.48 in repetition 1. `sobre-hooks` is native under another name on these tasks (same prompt, no compression), and it measured 0.97. Phase 2 needs more tasks and at least three repetitions, and an A/A arm that reports this noise directly.
4. **Lean-ctx, Headroom and rc.1 sobre stay above 1 on harder tasks too.** lean-ctx's tools invite more turns (11 against 7). Headroom writes more to the cache (24k tokens per run against 15k), which its rewriting of the prompt may cause.

   **Correction (2026-10-12).** Those extra writes were mostly cold starts. Headroom's rewritten prompt and lean-ctx's tools give each a prompt prefix of its own, which only its own runs warmed: they found it warm at 3 and 2 of their 12 starts, against every start for native, rtk and sobre, which share one prefix. With every session priced as if it had started cold, Headroom costs 0.99 (0.92–1.10), lean-ctx 1.35 (1.16–1.58), rtk 1.07 (0.93–1.31) and sobre 1.06 (0.97–1.18) ([cache-isolation.md](cache-isolation.md)).
5. **The cost model holds up:** a run costs $0.04 to $0.29, so a full phase 2 on these tasks fits the remaining API credit.

