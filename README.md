# trust-me-bro

> "Cuts your agent's token usage by up to 90%." Trust me, bro.

A paired benchmark of the tools that promise to make coding agents cheaper. It runs Claude Code on the same tasks, on the same code base, with and without each tool, and compares what matters: what the provider bills for the run, and whether the answer is still right.

## What it found

Claude Code 2.1.296, October 2026. Cost of a run relative to Claude Code alone: 1 is the same cost, above 1 costs more, below 1 costs less. Geometric mean of per-task cost ratios, with a 95% bootstrap interval (over tasks in pilots 1 and 2, over runs in pilot 5).

| Tool | Short tasks, Sonnet 5.5 ([pilot 1](docs/pilot-1.md)) | Harder tasks, Sonnet 5.5 ([pilot 2](docs/pilot-2.md)) | Long conversations, Haiku 5.5 ([pilot 5](docs/pilot-5.md)) | Long conversations, Sonnet 5.5 ([pilot 5](docs/pilot-5.md)) |
| --- | --- | --- | --- | --- |
| [rtk](https://github.com/rtk-ai/rtk) 0.51.0 | 1.06 (1.01–1.11) | 1.10 (0.91–1.44) | 1.48 (1.21–1.75) | 1.19 (1.05–1.35) |
| [Headroom](https://github.com/chopratejas/headroom) 0.40.0 | 1.14 (1.06–1.25) | 1.30 (1.22–1.40) | 0.89 (0.81–1.01) | 1.11 (0.98–1.22) |
| [lean-ctx](https://github.com/yvgude/lean-ctx) 3.11.2 | 1.62 (1.43–1.82) | 1.81 (1.52–2.11) | 1.78 (1.28–2.25) | 1.23 (1.16–1.31) |
| [sobre](https://github.com/malochapo/sobre-ai) 0.1.0-rc.1 | 1.13 (1.04–1.24) | 1.08 (0.96–1.23) | see below | see below |

Every run of pilots 1 and 2 succeeded, in every arm, and so did every Sonnet run of pilot 5. On Haiku's long conversations, rtk failed 3 runs of 12 and Claude Code alone 1.

One result sits at the edge of the noise: Headroom on Haiku's long conversations, 0.89 (0.81–1.01). Its proxy compresses tool results inside each request, and those runs read 15% fewer tokens from the cache. But its four tasks disagree (0.62 to 1.13), and on Sonnet it costs more.

sobre, written by this benchmark's author, was measured further in pilots 3 and 4 ([pilot 3](docs/pilot-3.md), [pilot 4](docs/pilot-4.md)). Its best build cost what Claude Code alone costs (0.98 to 1.03 on Sonnet's multi-turn conversations), and it was archived.

## Why they do not save

Measured across the 1,070 runs of pilots 1 to 5:

- **Every API call re-reads the whole prompt.** A tool result is written to the prompt cache once and read again at every later call. That is why tool results make up 28% to 50% of a run's cost ([pilot 4](docs/pilot-4.md)).
- **Agents already keep their outputs small.** Given megabytes of logs and full test suites, they pipe into `head`, `tail` and `grep -c`. Compressing what is left saves about 1% of a run ([pilot 2](docs/pilot-2.md), [pilot 4](docs/pilot-4.md)).
- **A tool's fixed cost is paid on every call.** Its tool definitions and instructions sit in the prompt prefix, and the extra turns it invites cost more than the bytes it removes. On long conversations, lean-ctx and rtk added 30% to 40% more turns ([pilot 1](docs/pilot-1.md), [pilot 5](docs/pilot-5.md)).
- **Agents do not use tools they are not told about.** In 454 runs with a context tool's MCP server connected, no agent called it unless a `CLAUDE.md` said to. Told to search with it, Haiku's runs cost 1.27 times more ([pilot 4](docs/pilot-4.md)).
- **The host's own features win.** Asked to save findings for the next day, every agent used Claude Code's own memory. Told to use an add-on memory instead, Sonnet's next day cost 1.23 times more ([pilot 4](docs/pilot-4.md)).
- **The lever that would matter belongs to the host.** In a long session, clearing old tool results from the prompt would cut about 20% of the cost on the same path. Claude Code clears them only once the cache has expired, and a tool outside the host cannot do it without breaking the cache ([docs/clearing.md](docs/clearing.md)).

## Who wrote this

The author of sobre, one of the tools measured. To keep that from tilting the results:
- the protocol is written before the runs ([PROTOCOL.md](PROTOCOL.md));
- every run is published with its transcript, failures included;
- each tool gets its vendor's documented default setup ([arms/README.md](arms/README.md));
- each tool's authors may review their arm and answer the results.

sobre was archived because of what this benchmark found.

## How it works

- **A real code base.** [Netflix Dispatch](https://github.com/Netflix/dispatch) (Apache-2.0, archived upstream), with commits planted in its history: facts that memory cannot supply, bugs to diagnose and fix, megabytes of logs. The build is deterministic ([fixture/](fixture/)).
- **Realistic tasks, graded.** Code questions, history questions, log diagnosis, bug fixes, cross-layer changes, multi-turn conversations, sessions compacted with `/compact`, work resumed the next day. Each is graded by expected facts, hidden tests or a blind judge. Every fact task is also run without the code, to check that memory cannot answer it.
- **Same agent, one variable.** Every arm runs the same pinned Claude Code, model, effort and limits. Each run starts in an empty home directory, with explicit settings and MCP configuration and no web access. The arms run interleaved, in a seeded random order, so that drift over time favors none.
- **Billed tokens only.** Each arm has its own API key, and a run billed to the wrong key is invalid. Cost is the run's tokens by class (input, output, cache reads, cache writes by lifetime) at public prices ([harness/prices.json](harness/prices.json)), subagents included. It is never an estimate of bytes saved.
- **Enough repetitions to see the noise.** Runs are paired by task, with at least two repetitions and bootstrap intervals. A/A arms measure the noise of the design itself.

## Repository map

| Path | What |
| --- | --- |
| [docs/](docs/) | one report per pilot, the run book, the clearing study |
| [tasks/](tasks/), [tasks2/](tasks2/), [tasks3/](tasks3/), [tasks4/](tasks4/) | the tasks of pilots 1, 2, 3 and 4; pilot 5 reuses pilot 4's long conversations |
| [results/](results/) | every run: `raw/` for pilot 1, then `pilot2/` to `pilot5/`. Each run keeps its transcript, usage, grade and metadata |
| [arms/](arms/) | how each tool is installed, set up and checked |
| [harness/](harness/) | runs, grading, usage, reports (Python 3.11, standard library only) |
| [fixture/](fixture/) | the build of the code base |

The arms named `sobre-*` are sobre's development builds. They are kept apart from the released tools in every report. [docs/sobre-dev.md](docs/sobre-dev.md) shows what they were for: measuring each change to a tool before shipping it.

## Run it

You need:
- Linux x86_64, git, Python 3.11 and 3.13, [uv](https://docs.astral.sh/uv/) and Claude Code;
- PostgreSQL on localhost (user `postgres`, password `dispatch`).

```sh
python3 -I fixture/build.py                     # build/fixture.git and build/plants.json
python3 -I fixture/gen_logs.py build            # build/data/log-dedup-regression/
uv venv -p 3.11 ~/.cache/trust-me-bro/deps
VIRTUAL_ENV=~/.cache/trust-me-bro/deps uv pip install -r fixture/requirements.lock hatchling versioningit editables
python3 -I tasks/validate.py --fixture build/fixture.git --deps-venv ~/.cache/trust-me-bro/deps
arms/install.sh                                 # every tool, at its pinned version
```

Then set one API key per arm (`BENCH_KEY_NATIVE`, `BENCH_KEY_RTK`, …) plus `BENCH_KEY_JUDGE`, and follow [harness/README.md](harness/README.md) and [docs/RUNBOOK.md](docs/RUNBOOK.md). A run costs $0.02 to $0.75 on Sonnet 5.5; each pilot report gives its total.

## Add your tool

An arm is a directory under `arms/` with three parts ([arms/README.md](arms/README.md) has the contract):
- a `setup.sh` that installs the tool the way its README tells Claude Code users to;
- a `probe.sh` that says whether the tool did anything during the run;
- its pinned version in `arms/versions.json`.

Open a pull request ([CONTRIBUTING.md](CONTRIBUTING.md)). If your tool documents a setup this benchmark does not follow, that is a bug in the benchmark.

## License

Apache-2.0. See [NOTICE](NOTICE) for the parts that come from Dispatch.
