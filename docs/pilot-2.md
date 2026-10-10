# Pilot 2: harder tasks

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
