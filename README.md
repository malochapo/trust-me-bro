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

The pilot (phase 1) has not run yet. No result exists.

## Why another benchmark

Published numbers for these tools mostly measure bytes saved on synthetic inputs, not what an agent pays to finish a task, nor whether it still finishes it. The few paired runs that exist found effects smaller than their own run-to-run variance. This benchmark counts the tokens of whole agent runs, grades their outcome, and repeats runs enough to separate effect from noise.

## What is in it

- [fixture/](fixture/): the code base. It is [Netflix Dispatch](https://github.com/Netflix/dispatch) (Apache-2.0, archived in 2025, so it no longer changes): a FastAPI backend, a Vue frontend and a signal-ingestion pipeline. Seven commits are planted in its real history: facts that memory cannot supply and bugs to diagnose or fix. The build is deterministic: the same inputs give the same commit ids.
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

Running the benchmark itself is described in [harness/README.md](harness/README.md).

## License

Apache-2.0. See [NOTICE](NOTICE) for the parts that come from Dispatch.
