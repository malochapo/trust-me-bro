# Harness

Paired runs of Claude Code (`claude-sonnet-5-5`) on the same tasks and the same code
base, once per arm (`native`, `sobre`, `lean-ctx`, `headroom`, `rtk`; see
`arms/README.md`). Python 3.11, standard library only; run every script with
`python3 -I`.

| file | what it does |
|---|---|
| `run.py` | one run: (task, arm, rep) → `results/raw/<run_id>/` |
| `grade.py` | grades a run dir → `graded.json` (facts, tests, judge) |
| `judge.py` | blind LLM judge for free-text answers (used by `grade.py`) |
| `usage.py` | tokens per model and class, cost (measured, and with every session started on a cold cache), tool stats, from `stream.jsonl` |
| `report.py` | `results/report.md` and `results/report.csv` |
| `cache_isolation.py` | how often each arm's sessions started warm, and each pilot's ratios measured, cold and warm (`docs/cache-isolation.md`) |
| `bench.py` | runs a matrix in a seeded, interleaved order, then grades it |
| `prices.json` | $ per million tokens per model (to verify against the public pricing page) |
| `common.py` | shared helpers: clean env, lock, run virtualenv, Postgres check |
| `tests/` | unittest suite; `fake_claude.py` stands in for `claude` |

## Prerequisites

- Linux x86_64 (glibc >= 2.35 for the lean-ctx build), `git`, `curl`, [`uv`](https://docs.astral.sh/uv/),
  Python 3.11 and 3.13, Claude Code (`claude --version`).
- Postgres on `localhost:5432`, user `postgres`, password `dispatch` (the fixture's
  tests create and drop the database `dispatch-test`). One database for everything,
  so runs and grading are strictly sequential: `run.py` and the tests grader take the
  lock `/tmp/trust-me-bro.lock` (`BENCH_LOCK_FILE`), and `run.py`/`bench.py` refuse to
  start when `pg_isready -h localhost` fails.
- Running as root: Claude Code refuses `bypassPermissions` as root outside a sandbox;
  the harness sets `IS_SANDBOX=1` for the agent. Run in a container or VM.

## Set up once

```bash
# 1. The arms' tools, at the pinned versions (idempotent), into $BENCH_TOOLS
#    (default ~/.cache/trust-me-bro/tools)
arms/install.sh

# 2. The fixture: build/fixture.git (bare, branch main), build/plants.json, build/data/
python3 -I fixture/build.py

# 3. Dispatch's dependencies, once, in a shared virtualenv without Dispatch itself
export BENCH_DEPS_VENV=$HOME/.cache/trust-me-bro/deps
uv venv -p 3.11 "$BENCH_DEPS_VENV"
uv pip install --python "$BENCH_DEPS_VENV/bin/python" -r fixture/requirements.lock hatchling versioningit editables

# 4. Credentials, under BENCH_ names so they cannot interfere with a Claude Code
#    session you run the harness from. Either one API key per arm and one for the judge,
#    so the console bills each arm on its own:
export BENCH_KEY_NATIVE=... BENCH_KEY_SOBRE=... BENCH_KEY_LEANCTX=... \
       BENCH_KEY_HEADROOM=... BENCH_KEY_RTK=... BENCH_KEY_JUDGE=...
#    or a Claude subscription token (from `claude setup-token`) for whatever has no key:
export BENCH_CLAUDE_OAUTH_TOKEN=...   # CLAUDE_CODE_OAUTH_TOKEN works as a fallback
```

The agent receives a key only as `ANTHROPIC_API_KEY` and a token only as
`CLAUDE_CODE_OAUTH_TOKEN`. A machine can also supply Claude Code with credentials of
its own (a Claude Code cloud session does, even to a child with an empty environment).
An API key takes precedence over those; the harness checks the run's `apiKeySource`
and marks the run invalid when it was not billed to the arm's key. A subscription
token cannot be told apart from such machine credentials, so on such a machine prefer
API keys, or run where no credentials are supplied.

## Run a pilot

```bash
# One run, then grade it
python3 -I harness/run.py --task-file tasks/qa-default-dedup-window/task.json --arm native --rep 1
python3 -I harness/grade.py results/raw/qa-default-dedup-window__native__r1

# A small matrix: plan first, then run and grade, then the report
python3 -I harness/bench.py --tasks 'tasks/qa-*/task.json,tasks/log-*/task.json' --arms native,sobre --reps 1 --dry-run
python3 -I harness/bench.py --tasks 'tasks/qa-*/task.json,tasks/log-*/task.json' --arms native,sobre --reps 1
python3 -I harness/report.py
```

`run.py` options (defaults): `--fixture build/fixture.git`, `--out results/raw`,
`--work /tmp/trust-me-bro-work`, `--model claude-sonnet-5-5`, `--effort medium`,
`--max-turns 80`, `--max-budget-usd 8`, `--timeout-min 25`, `--claude-bin claude`,
`--deps-venv $BENCH_DEPS_VENV`, `--cleanup` (delete the work dir afterwards; grading
a tests task needs it), `--force` (replace an existing run dir). `bench.py` passes
anything after `--` to `run.py` (`-- --effort high`), re-runs invalid runs, skips
the rest (`--rerun-errors` also re-runs timeouts and errors), and grades every ok run
without `graded.json`. `report.py --margin-pp 5 --resamples 10000 --seed 20261010`.

Run the tests (no token, no network; `test_arms.py` sets up each installed arm for
real, `test_grade.py`'s tests-grader case needs Postgres):

```bash
python3 -I -m unittest discover -s harness/tests
```

## What a run does

1. Makes `work/run-<hash>/{repo,home,data,venv,bin}`. The name is a hash of the run id
   on purpose: the agent sees its cwd, HOME and data paths, and they must not name the arm.
2. `git clone` of the fixture into `repo`, remote removed; copies the task's data
   (`task.json` `data`: a path relative to the bench root, or `true` for
   `tasks/<id>/data`) into `data`; `{DATA_DIR}` in the prompt becomes its absolute path.
3. The run's virtualenv: `uv venv -p 3.11`, a `.pth` to `$BENCH_DEPS_VENV`'s
   site-packages, and `uv pip install --no-deps --no-build-isolation -e repo`, so
   `import dispatch` is the run's own checkout. `venv/bin` is first on the agent's PATH.
4. `arms/<arm>/setup.sh` in the fresh `home` (contract in `arms/README.md`).
5. `claude -p <prompt> --model M --effort E --output-format stream-json --verbose
   --setting-sources user --strict-mcp-config --mcp-config $HOME/mcp.json
   --permission-mode bypassPermissions --max-turns N --max-budget-usd B
   --disallowedTools WebFetch WebSearch`, cwd = `repo`, in its own process session.
   On timeout: SIGINT (Claude Code then still writes its result event), then SIGTERM,
   SIGKILL. Whatever the agent left running in its session is killed afterwards.
6. `arms/<arm>/probe.sh`, then the arm's daemon (`home/arm.pid`) is stopped.

The agent's environment is built from nothing, never from the harness's: `PATH`
(`venv/bin`, `bin/` with only this arm's tool, `$BENCH_EXTRA_PATH`, then
`/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin`), `HOME`,
`CLAUDE_CONFIG_DIR=$HOME/.claude`, `LANG=C.UTF-8`, `TERM=dumb`, `IS_SANDBOX=1`,
`DISABLE_AUTOUPDATER=1`, the credentials (`ANTHROPIC_API_KEY` or
`CLAUDE_CODE_OAUTH_TOKEN`), plus the arm's extra env. No
`CLAUDE_*`/`ANTHROPIC_*` variable of the caller and no `HTTP(S)_PROXY` reach it, so
the agent has no proxy to the internet (it may still reach hosts the network routes
directly; WebFetch and WebSearch are disallowed). A run whose Bash commands look like
network access (curl, wget, git clone/fetch/pull, pip or npm installs, URLs other than
localhost) gets the flag `network_command`, with the commands in `meta.json`; the agent
could otherwise fetch upstream Dispatch and diff away the planted changes. setup.sh and
probe.sh get the same environment minus the credentials and `venv/bin`, plus `REPO` and
`BENCH_TOOLS`.

## Status

- `invalid`: the run did not test what it should, and is re-run, never scored. setup.sh
  failed; no `system/init` event; the init model is not the requested one; permission
  mode is not `bypassPermissions`; an MCP server from `mcp.json` is not `connected`, is
  missing, or an unexpected one is present, or `mcp_server_errors` is set; the main loop
  was answered by another model; the result is an API error (auth, usage limit); an
  API-key run was not billed to its key (`apiKeySource` is not `ANTHROPIC_API_KEY`); or
  the harness itself failed.
- `timeout`: killed at `--timeout-min`.
- `error`: no result event, or `error_during_execution`.
- `ok`: everything else, including `error_max_turns` and `error_max_budget_usd`
  (recorded as `result_subtype`; those are the agent's outcome and are graded).

A non-native run whose probe reports no activity gets the flag `probe_inactive`; it is
still scored, and the report lists it. The report scores `ok` runs by their grade, and
timeouts and errors as failures: running out of time or crashing is the arm's outcome,
and dropping those runs could favor an arm. Invalid runs are never scored.

## What a run dir holds (`results/raw/<task>__<arm>__r<rep>/`)

| file | content |
|---|---|
| `meta.json` | run id, task id, task file and its sha256, family, grader kind, arm, rep, model, effort, CLI flags, the exact command (prompt as `<prompt.txt>`), `claude --version`, the arm's entry from `arms/versions.json`, fixture path and HEAD sha, work paths, extra env, setup exit code and seconds, start/end UTC, wall seconds, exit code, timed_out, init summary (model, tools, MCP server statuses, skills), probe_active, flags, untracked files, agent commits, result subtype, status, invalid_reason |
| `prompt.txt` | the exact prompt given to the agent |
| `stream.jsonl` | Claude Code's stdout (stream-json events) |
| `stderr.txt` | Claude Code's stderr |
| `answer.md` | the final answer: the `result` event's `result` |
| `changes.patch` | the repo's diff against the fixture commit (commits the agent made included), then each untracked file as a new-file diff; untracked paths listed at the top |
| `usage.json` | `usage.py` output (below) |
| `probe.json` | the arm's probe output |
| `setup.log` | virtualenv build, setup.sh stdout and stderr |
| `arm/` | the `settings.json`, `mcp.json` and `CLAUDE.md` the agent was given |
| `graded.json` | `grade.py`: kind, pass, score (0-1), details, task sha256, time |
| `grade_tests.log`, `grade_regression.log` | tests grader output |
| `judge_prompt.txt`, `judge_reply.json` | judge grader: exact prompt and raw reply |

The work dir (`/tmp/trust-me-bro-work/run-<hash>/`, path in `meta.json`) keeps the
repo as the agent left it, its HOME and the virtualenv.

## Tokens and cost (`usage.py`)

- Per model: input, output, cache read, cache write 5m, cache write 1h. Totals come
  from the `result` event's `modelUsage`, which includes subagents.
- The 5m/1h split of cache writes comes from `usage.cache_creation` of the assistant
  events, each API response counted once (a message id repeats when one response has
  several tool calls), and is applied to the `modelUsage` total. When a model has no
  split, its writes count as 1h writes (what a subscription gets) and
  `cache_write_split_assumed_1h:<model>` is flagged. Without a result event, totals
  come from the messages and output tokens are placeholders (flag `no_model_usage`).
- Cost = tokens × `prices.json`; model ids are priced by exact key or the longest key
  they start with (`unpriced_model:<id>` otherwise). `client_total_cost_usd` is
  Claude Code's own estimate, for cross-checking.
- Also: `num_turns`, `duration_ms`, `duration_api_ms`, tool calls per tool name,
  tool results, those with `is_error`, and the characters of tool-result text the
  model received.
- `cost_cold_usd` and `cold_start`: the run's cost had each session started on a cold
  prompt cache. The keys of a workspace share the cache, so a session's first response
  can read a prefix another run wrote (Claude Code's tool definitions and system
  prompt). The first response of each session, and of each subagent type's first spawn
  (forks excepted), has its cache reads priced as the cache writes they would have been;
  every later response reads what its own run wrote and is unchanged
  ([docs/cache-isolation.md](../docs/cache-isolation.md)). For a run recorded before the field
  existed, `usage.cold_cost()` computes it from the stream.

`python3 -I harness/usage.py <run dir>` prints it.

## Grading (`grade.py`)

- `facts`: `grader.must` = `[{id, any_of: [regex]}]`, `grader.must_not` = `[{id, regex}]`,
  searched in `answer.md` case-insensitively, multi-line. `{plant:<id>}` and
  `{plant:<id>:short}` (first 8 chars) in a regex become that plant's commit sha from
  `build/plants.json`. Score = matched / len(must); pass = all must, no must_not.
- `tests`: copies `tasks/<id>/hidden/` over the run's repo, runs `grader.command` in it
  (run's `venv/bin` first on PATH, clean env, a temporary HOME, 15 min timeout), then
  `grader.regression`, by default `python -m pytest -q -p no:cacheprovider tests/signal`
  (`[]` for none). Pass = both exit 0. Takes the bench lock and checks Postgres.
- `judge`: `judge.py`. The prompt has the question, `grader.reference`, `grader.rubric`
  (0-3) and the answer with `sobre`, `lean-ctx`/`lean_ctx`/`leanctx`, `headroom`, `rtk`,
  `mcp__…`, `ctx_…`, `sobre_…` and headroom's `<<ccr:…>>` markers replaced by `[tool]`.
  It runs `claude -p --tools "" --output-format json --json-schema {score, reasons}
  --model <--judge-model>` with an empty config dir, a neutral cwd and a clean env.
  Score = score / 3; pass = score >= `grader.pass_score` (default 2).

Invalid runs are refused; `--force` re-grades.

## Report (`report.py`)

Per arm over scored runs (graded `ok` runs, plus timeouts and errors as failures): runs, success rate, cost mean and median (and the client
estimate), mean tokens per class, turns, wall time, tool calls. Each arm is paired
with native per task (each task's mean over its reps); 10,000 bootstrap resamples of
tasks with a fixed seed give 95% percentile intervals for Δ success (percentage
points) and for the cost ratio (geometric mean of per-task ratios). Verdict on
success with margin M: non-inferior if the interval's lower bound is above -M,
inferior if its upper bound is below -M, inconclusive otherwise. Then a per-task
table, run status counts per arm, and the runs not scored or flagged. The per-arm
table adds the mean cold-start cost, and the paired table the cold-start cost ratio
with its interval, from the same resamples (`usage.py`'s `cost_cold_usd`).
