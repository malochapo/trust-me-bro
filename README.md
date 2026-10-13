# trust-me-bro

> "Cuts your agent's token usage by up to 90%." Trust me, bro.

A paired benchmark of the tools that promise to make coding agents cheaper. It runs Claude Code on the same tasks, on the same code base, with and without each tool, and compares what matters: what the provider bills for the run, and whether the answer is still right.

## What it found

Claude Code 2.1.296, October 2026. Cost of a run relative to Claude Code alone: 1 is the same cost, above 1 costs more, below 1 costs less. Every session is priced as if it had started on a cold prompt cache: interleaved arms share the cache, and the arms that change Claude Code's prompt prefix found it warm less often than native ([docs/cache-isolation.md](docs/cache-isolation.md)). Geometric mean of per-task cost ratios, with a 95% bootstrap interval (over tasks in pilots 1 and 2, over runs in pilot 5).

| Tool | Short tasks, Sonnet 5.5 ([pilot 1](docs/pilot-1.md)) | Harder tasks, Sonnet 5.5 ([pilot 2](docs/pilot-2.md)) | Long conversations, Haiku 5.5 ([pilot 5](docs/pilot-5.md)) | Long conversations, Sonnet 5.5 ([pilot 5](docs/pilot-5.md)) |
| --- | --- | --- | --- | --- |
| [rtk](https://github.com/rtk-ai/rtk) 0.51.0 | 1.04 (1.00–1.08) | 1.07 (0.93–1.31) | 1.47 (1.20–1.74) | 1.18 (1.05–1.33) |
| [Headroom](https://github.com/chopratejas/headroom) 0.40.0 | 1.00 (0.97–1.03) | 0.99 (0.92–1.10) | 0.87 (0.79–0.98) | 1.07 (0.97–1.16) |
| [lean-ctx](https://github.com/yvgude/lean-ctx) 3.11.2 | 1.40 (1.31–1.49) | 1.35 (1.16–1.58) | 1.74 (1.26–2.20) | 1.18 (1.12–1.25) |
| [sobre](https://github.com/malochapo/sobre-ai) 0.1.0-rc.1 | 1.08 (1.02–1.16) | 1.06 (0.97–1.18) | see below | see below |

As billed, with whatever cache each run happened to find, the same runs gave rtk 1.06, 1.10, 1.48 and 1.19; Headroom 1.14, 1.30, 0.89 and 1.11; lean-ctx 1.62, 1.81, 1.78 and 1.23; sobre 1.13 and 1.08. The gap is Headroom's and lean-ctx's: native, rtk and sobre share one prompt prefix and found it warm at every start, while those two found theirs warm at 8% to 80% of their starts. Priced the other way, every session warm, gives the same picture.

Every run of pilots 1 and 2 succeeded, in every arm, and so did every Sonnet run of pilot 5. On Haiku's long conversations, rtk failed 3 runs of 12 and Claude Code alone 1.

Headroom is the one tool below 1: 0.87 (0.79–0.98) on Haiku's long conversations. Its proxy compresses tool results inside each request, and those runs read 15% fewer tokens from the cache. But its four tasks disagree (0.62 to 1.13 as billed), on Sonnet it costs 1.07 (0.97–1.16), and on short tasks it costs what Claude Code alone costs.

sobre, written by this benchmark's author, was measured further in pilots 3 and 4 ([pilot 3](docs/pilot-3.md), [pilot 4](docs/pilot-4.md)). Its best build cost what Claude Code alone costs (0.98 to 1.03 on Sonnet's multi-turn conversations), and it was archived.

## Why they do not save

Measured across the 1,116 runs of pilots 1 to 5, all published here:

- **Every API call re-reads the whole prompt.** A tool result is written to the prompt cache once and read again at every later call. That is why tool results make up 28% to 50% of a run's cost ([pilot 4](docs/pilot-4.md)).
- **Agents already keep their outputs small.** Given megabytes of logs and full test suites, they pipe into `head`, `tail` and `grep -c`. Compressing what is left saves about 1% of a run ([pilot 2](docs/pilot-2.md), [pilot 4](docs/pilot-4.md)).
- **A tool's fixed cost is paid on every call.** Its tool definitions and instructions sit in the prompt prefix, and the extra turns it invites cost more than the bytes it removes. On long conversations, lean-ctx and rtk added 30% to 40% more turns ([pilot 1](docs/pilot-1.md), [pilot 5](docs/pilot-5.md)).
- **Agents use a context tool only when its tools are in the prompt, and then pay for them.** In 454 runs with a context tool's MCP server connected, no agent called it unless a `CLAUDE.md` said to. Told to search with it, Haiku's runs cost 1.27 times more ([pilot 4](docs/pilot-4.md)). Claude Code had deferred those tools behind its tool search, so the agent saw only their names. Loaded up front, Haiku and Sonnet used them on search questions with no instruction, for 1.20 to 1.40 times the cost and the same answers; in Haiku's long sessions they were seldom used and still added 6%. Their definitions ride on every request, and the agent used them to grep, never to search by meaning ([docs/mcp-visibility.md](docs/mcp-visibility.md)).
- **The host's own features win.** Asked to save findings for the next day, every agent used Claude Code's own memory. Told to use an add-on memory instead, Sonnet's next day cost 1.23 times more ([pilot 4](docs/pilot-4.md)).
- **The lever that would matter belongs to the host.** In a long session, clearing old tool results from the prompt would cut about 20% of the cost on the same path. Claude Code clears them only once the cache has expired, and a tool outside the host cannot do it without breaking the cache ([docs/clearing.md](docs/clearing.md)).
- **Interleaved arms share the prompt cache.** A session starts by reading or writing Claude Code's tool definitions and system prompt, the same in every run of a setup, and every key of a workspace shares the cache. As billed, that put 14 and 31 points on Headroom's short tasks and 22 and 46 on lean-ctx's, whose prefixes no other arm warmed ([docs/cache-isolation.md](docs/cache-isolation.md)).

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
- **Billed tokens only.** Each arm has its own API key, and a run billed to the wrong key is invalid. Cost is the run's tokens by class (input, output, cache reads, cache writes by lifetime) at public prices ([harness/prices.json](harness/prices.json)), subagents included. It is never an estimate of bytes saved. Because the keys of a workspace share the prompt cache, reports also price each run as if its sessions had started cold, which does not depend on the runs before it ([docs/cache-isolation.md](docs/cache-isolation.md)).
- **Enough repetitions to see the noise.** Runs are paired by task, with at least two repetitions and bootstrap intervals. A/A arms measure the noise of the design itself.

## Repository map

| Path | What |
| --- | --- |
| [docs/](docs/) | one report per pilot, the run book, the clearing study, the cache-isolation and MCP-visibility notes |
| [tasks/](tasks/), [tasks2/](tasks2/), [tasks3/](tasks3/), [tasks4/](tasks4/), [tasks5/](tasks5/) | the tasks of pilots 1, 2, 3 and 4; pilot 5 reuses pilot 4's long conversations; `tasks5/` moves their `/compact` ([docs/compaction-position.md](docs/compaction-position.md)) |
| [results/](results/) | every run: `raw/` for pilot 1, then `pilot2/` to `pilot5/`, `mcp-always/` for the MCP visibility test and `compaction-position/` for the compaction position test. Each run keeps its transcript, usage, grade and metadata |
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
