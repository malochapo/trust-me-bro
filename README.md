# sobre-bench

A paired benchmark of context tools for coding agents. It runs Claude Code on the same tasks, on the same code base, under five setups ("arms"), and measures two things: what each run costs, and whether its answer is right.

| Arm | Setup |
| --- | --- |
| `native` | Claude Code alone |
| `sobre` | [sobre](https://github.com/malochapo/sobre-ai) |
| `lean-ctx` | [lean-ctx](https://github.com/yvgude/lean-ctx) |
| `headroom` | [Headroom](https://github.com/chopratejas/headroom), proxy mode |
| `rtk` | [rtk](https://github.com/rtk-ai/rtk) |

Each tool gets its vendor's documented default setup for Claude Code, nothing more ([arms/README.md](arms/README.md)).

sobre's maintainer wrote this benchmark. To keep that from tilting it, the protocol is fixed before any scored run ([PROTOCOL.md](PROTOCOL.md)). Every run is published, failures included, and each tool's authors may review their arm's setup and answer the results.

## Status

- **Pilot 1 is done** ([docs/pilot-1.md](docs/pilot-1.md)): 100 runs, all successful. Its tasks were too easy to separate the arms on success. On cost, against Claude Code alone: rtk 1.06, sobre 1.13, Headroom 1.14, lean-ctx 1.62.
- **Pilot 2 is done** ([docs/pilot-2.md](docs/pilot-2.md)): 84 runs on harder tasks, all successful again. On cost, against Claude Code alone: sobre 1.08, rtk 1.10, Headroom 1.30, lean-ctx 1.81, with wide intervals over 6 tasks.
- **Pilot 3 is done** ([docs/pilot-3.md](docs/pilot-3.md)): 488 runs on Sonnet 5.5 and Haiku 5.5, with four multi-turn conversations, measuring sobre at compression levels 0.3, 0.6 and 0.9 against Claude Code alone. sobre costs what Claude Code alone costs (Sonnet 0.98 to 1.03; Haiku within the spread of an A/A control). One log-diagnosis conversation came out 12% cheaper with sobre (p = 0.09).
- **sobre's development arms** ([docs/sobre-dev.md](docs/sobre-dev.md)) measure a build of sobre that removes rc.1's overhead. It costs what Claude Code alone costs: 1.02 on pilot 1 and 1.01 on pilot 2, against 1.13 and 1.08 for rc.1. They are kept apart from the released tools' results.

## Why another benchmark

Published numbers for these tools mostly measure bytes saved on synthetic inputs, not what an agent pays to finish a task, nor whether it still finishes it. The few paired runs that exist found effects smaller than their own run-to-run variance. This benchmark counts the tokens of whole agent runs, grades their outcome, and repeats runs enough to separate effect from noise.

## What is in it

- [fixture/](fixture/): the code base. It is [Netflix Dispatch](https://github.com/Netflix/dispatch) (Apache-2.0, archived in 2025, so it no longer changes): a FastAPI backend, a Vue frontend and a signal-ingestion pipeline. Eight commits are planted in its real history: facts that memory cannot supply and bugs to diagnose or fix. The build is deterministic: the same inputs give the same commit ids.
- [tasks/](tasks/): ten pilot tasks across six families: code questions, a cross-layer question, a frontend question, a git-history question, log diagnosis, bug fixes and a cross-layer change. They are graded by expected facts, hidden tests or a blind judge. `tasks/validate.py` checks each task against its reference answer.
- [harness/](harness/): runs one task under one arm in an isolated home directory, collects token usage from Claude Code's output, grades the run and builds the report.
- [arms/](arms/): installs each tool at a pinned version and configures it per run.

## Build and check

Needs git, Python 3.11, [uv](https://docs.astral.sh/uv/) and PostgreSQL on localhost (user `postgres`, password `dispatch`).

```sh
python3 -I fixture/build.py                     # build/fixture.git and build/plants.json
python3 -I fixture/gen_logs.py build            # build/data/log-dedup-regression/
uv venv -p 3.11 ~/.cache/sobre-bench/deps
VIRTUAL_ENV=~/.cache/sobre-bench/deps uv pip install -r fixture/requirements.lock hatchling versioningit editables
python3 -I tasks/validate.py --fixture build/fixture.git --deps-venv ~/.cache/sobre-bench/deps
```

Running the benchmark itself is described in [harness/README.md](harness/README.md). The steps for phases 0 and 1 are in [docs/RUNBOOK.md](docs/RUNBOOK.md).

## License

Apache-2.0. See [NOTICE](NOTICE) for the parts that come from Dispatch.
