# Runbook: phase 0 and the pilot

How to run phases 0 and 1 from a fresh machine or a fresh Claude Code cloud session. Every command runs from the repository root.

## Credentials

The pilot uses one API key per arm, plus one for the judge and the leakage check. They are environment variables:

```
BENCH_KEY_NATIVE  BENCH_KEY_SOBRE  BENCH_KEY_LEANCTX  BENCH_KEY_HEADROOM  BENCH_KEY_RTK  BENCH_KEY_JUDGE
```

All keys belong to one Console workspace, which has a spend limit. The pilot's budget is the $100 of API credit.

Claude Code cloud sessions supply Claude Code with credentials of their own, even to a child process started with an empty environment. An explicit API key takes precedence over them. The harness checks that each run was billed to its arm's key (`apiKeySource`) and marks the run invalid otherwise. Never run the bench there without the keys: it would bill the session's subscription and measure nothing per arm.

## Prepare the machine (once per container)

```sh
# PostgreSQL for the fixture's tests
pg_ctlcluster 16 main start
su postgres -c "psql -c \"ALTER USER postgres PASSWORD 'dispatch';\""

# Fixture and its data
python3 -I fixture/build.py
python3 -I fixture/gen_logs.py build

# Dispatch's dependencies, shared by every run's venv
export BENCH_DEPS_VENV=~/.cache/trust-me-bro/deps
uv venv -q -p 3.11 "$BENCH_DEPS_VENV"
uv pip install -q --python "$BENCH_DEPS_VENV/bin/python" -r fixture/requirements.lock hatchling versioningit editables

# The arms' tools, at their pinned versions
bash arms/install.sh

# Checks
python3 -I tasks/validate.py --fixture build/fixture.git --deps-venv "$BENCH_DEPS_VENV"   # 9 ok
python3 -I -m unittest discover -s harness/tests                                         # OK
```

## Phase 0: leakage check

```sh
python3 -I harness/leakage.py --reps 3
```

This puts each fact task to the model with no repository and no tools. Any task marked `LEAKED` is answerable without the code: rewrite it or drop it before the pilot, and record the change in PROTOCOL.md's changelog. The check costs well under $1.

## Phase 1: the pilot

Run each arm once on one cheap task, and look at all five runs before going further:

```sh
python3 -I harness/bench.py --tasks 'tasks/qa-cases-page-size/task.json' --arms native,sobre,lean-ctx,headroom,rtk --reps 1
```

For each run directory under `results/raw/`, check:
- `meta.json`: `status` is `ok`, `init.apiKeySource` is `ANTHROPIC_API_KEY`, and the MCP servers are `connected`;
- `probe.json`: it shows the arm was active;
- `usage.json`: the cost is plausible.

Then run the first repetition of every task: 50 runs. Runs already done are skipped.

```sh
python3 -I harness/bench.py --tasks 'tasks/*/task.json' --arms native,sobre,lean-ctx,headroom,rtk --reps 1
```

Watch the spend:
- **On the Console:** after about 25 runs, compare the spend with the sum of `usage.json` costs. If the projected total for 50 runs passes $90, stop.
- **The cap:** each run stops at $3 (`--max-budget-usd`), and the workspace's spend limit is the hard stop.
- **Rate limits:** a low API tier can rate-limit Claude Code. A run that ends on an API error is marked invalid, and `bench.py` runs it again.

If enough credit is left, run a second repetition (`--reps 2` skips the first). Then:

```sh
python3 -I harness/report.py        # results/report.md and results/report.csv
```

## After the pilot

- **Cost check:** compare each arm's billed cost on the Console, by API key, with the arm's summed `usage.json` cost. Report the gap: it validates the cost formula that phase 2 uses on a subscription.
- **Results:** commit `results/report.md`, `results/report.csv` and the raw run directories (`results/raw/`; mind their size).
- **Summary:** post a short summary on malochapo/sobre-ai issue #81 that links to the report. It must say what the pilot is not: 10 tasks and one or two repetitions, which estimate variance and cost and back no claim.
- **Phase 2:** choose the number of tasks and repetitions from the pilot's variance, then freeze PROTOCOL.md.

## Parallel runs (`bench.py --jobs N`)

Each job needs its own Postgres server, on consecutive ports from `--first-port`. Create them UTF8, since Dispatch's tests create a UTF8 database from `template1`:

```sh
for port in 5436 5437 5438; do
  pg_createcluster 16 bench$port -p $port --encoding UTF8 --locale C.UTF-8 --start
  su postgres -c "psql -p $port -c \"ALTER USER postgres PASSWORD 'dispatch'\""
done
python3 -I harness/bench.py ... --jobs 3 --first-port 5436
```

`bench.py` refuses to start when a server's `template1` is not UTF8. A container restart stops the clusters: `pg_ctlcluster 16 <name> start`.
