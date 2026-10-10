# Protocol

This is a draft for the pilot (phase 1). It will be frozen before phase 2, the first phase whose results are published as findings. After that, any change is logged in the changelog at the end of this file, with its reason.

## Question

With Claude Code and Sonnet 5.5, does each tool lower the cost of completing realistic tasks on a real code base, without lowering the share of tasks completed?

## Arms

`native`, `sobre`, `lean-ctx`, `headroom`, `rtk`. Each one gets its vendor's documented default setup for Claude Code, at the version pinned in `arms/versions.json`. Headroom runs in proxy mode, not through `headroom wrap`, because `wrap` also adds the Serena MCP server, which would make it a different tool. It is installed with its `[sandbox]` extra: its documented torch-free bundle, which keeps code-aware compression and Kompress (through ONNX). The `[all]` extra would add torch and features that do not apply to a single run, such as memory, images and voice. Any tool that documents a one-time index or warm-up step gets it before the run starts, so every run starts warm.

## Fixed run settings

These are the same for every arm:
- **Model and effort:** `claude-sonnet-5-5` at effort `medium`. Claude Code is pinned to one version.
- **Limits:** at most 80 turns, a $3 budget cap and a 25-minute timeout per run.
- **Isolation:** each run gets an empty home directory, its own `CLAUDE_CONFIG_DIR`, explicit settings and MCP configuration (`--setting-sources user --strict-mcp-config`), and an environment rebuilt from scratch. Permissions are bypassed.
- **No web:** WebFetch and WebSearch are disabled, and the agent's shell gets no proxy. Some hosts may still be reachable directly, so any run whose shell commands look like network access (curl, wget, git clone/fetch/pull, package installs, URLs) is flagged and listed in the report. That way, an agent that fetched upstream Dispatch to diff away the planted changes is visible.
- **Authentication:** one API key per arm, so the console bills each arm separately, or else a Claude subscription token. A run that should have been billed to its arm's key but was not (its `apiKeySource` shows otherwise) is invalid. Cache writes are counted with their actual lifetime (5 minutes or 1 hour), whatever Claude Code uses with that authentication.
- **Ordering:** the arms run in an interleaved order shuffled with a fixed seed, so drift over time (API load, caching, model serving) does not favor one arm.

## Fixture

Netflix Dispatch at `dd2837e8`, with 150 commits replayed and 8 commits planted among them (`fixture/plants.json`). The build is deterministic and checks that its final tree equals upstream plus the plants.

## Tasks and grading

The pilot has 10 tasks:
- **Facts (6 tasks):** the answer ends with labeled lines, matched by regular expressions. Each task ships a reference answer that must pass and the answer that memory or upstream code gives, which must fail.
- **Hidden tests (3 tasks):** these tests fail on the fixture and pass with the reference fix. The regression suite must pass too.
- **Blind judge (1 task):** Claude Sonnet 5.5 scores 0–3 against a reference and a rubric. It never sees the arm, and names that would reveal the arm are masked in the answer.

A run succeeds when its grader passes, or when the judge gives it 2 or more. A run that times out or crashes counts as a failure, and its cost counts too: those are the arm's outcomes, and dropping them could favor an arm.

## Outcomes

- **Primary:**
  1. Success rate.
  2. Cost per run in USD: the run's tokens by class (input, output, cache read, cache write at 5 minutes and 1 hour, subagents included), multiplied by public API prices (`harness/prices.json`). Subscription runs have no bill, so this is an API-equivalent cost. It is the same formula for every arm.
- **Secondary:** tokens by class, turns, wall time, failed tool calls.

## Analysis

- **Pairing:** comparisons are paired by task. Each task's value is the mean over its repetitions.
- **Confidence intervals:** 95% intervals come from 10,000 bootstrap resamples over tasks, with a fixed seed.
- **Success:** the difference in success rate against `native`, in percentage points. Non-inferiority is judged with a margin of −5 points. The pilot reports it but draws no conclusion from it.
- **Cost:** the geometric mean of the per-task cost ratios against `native`.

## Validity

- **Run checks:** a run is invalid if its `system/init` event does not show the expected model and every MCP server of its arm connected, if the API failed, or if it was billed to the wrong credentials. Invalid runs are re-run and never scored, but the report lists them. A run whose arm probe shows no activity is flagged, still scored, and listed.
- **Leakage check (phase 0):** each fact task is put to the model with no repository and no tools. A task it answers correctly is dropped.
- **Judge calibration (phase 2):** a person scores about 50 judged answers blind, and the report gives the agreement (Cohen's kappa).

## Phases

- **Phase 0:** the leakage check (`harness/leakage.py`).
- **Phase 1, the pilot:** it runs on $100 of API credit, with one key per arm, so each arm's billed cost can be checked against the cost formula. First, one run per arm on a single task, inspected by hand. Then 10 tasks × 5 arms × 1 repetition = 50 runs, plus a second repetition if the credit allows. The pilot checks the harness and estimates variance and cost, which set the number of tasks and repetitions for phase 2. It makes no claims. The steps are in [docs/RUNBOOK.md](docs/RUNBOOK.md).
- **Phase 2:** 40 to 60 tasks × 5 arms × 3 or more repetitions, under this protocol frozen.
- **Phase 3:** a subset of SWE-QA-Pro, as an external task set.

## Known limits

- **Narrow scope:** one model, one agent (Claude Code) and one code base (Python and Vue).
- **Cost:** it is API-equivalent, not billed, and measured on a subscription whose limits can throttle runs.
- **Moving targets:** the tools change quickly. Results hold for the pinned versions only.
- **Conflict of interest:** the maintainer of sobre wrote the benchmark. Mitigations:
  - this protocol is fixed before scored runs;
  - every run is published, raw data included;
  - each tool's authors may review their arm's setup and answer the results.

## Changelog

- 2026-10-10: first draft.
- 2026-10-10:
  - per-arm API keys, with a check that each run was billed to its key;
  - timeouts and crashes are scored as failures;
  - shell network access is flagged;
  - Headroom is installed with `[sandbox]`.
- 2026-10-10: the pilot runs on API credit, with a $3 cap per run and one repetition, plus a second if the credit allows.
- 2026-10-10, phase 0 (`results/leakage/`, `results/leakage-v2/`):
  - five of the six fact tasks were never answered correctly without the code (0/3 each);
  - `qa-ui-entity-stats` was answered from memory 3/3. It now also asks for the period the counts cover, which plant `p6-entity-stats-window` sets to 30 days. The rewritten task scored 0/3 without the code: the model guessed 7 days.
- 2026-10-10, during the pilot's first repetition, three grader defects rejected correct answers. All three were fixed, and every fact-graded run was re-graded with the final rules, the same for every arm:
  - `INSTANCE_WINDOW: 30` was refused because the rule wanted "30 days", although the requested format is a number of days;
  - `GET signals/stats` was refused for lacking the leading slash. Path rules now accept any correct way of writing the path: `FILE` in three tasks, `ENDPOINT`, and `REDACTION_FUNCTION`;
  - the rule meant to reject a per-signal endpoint also matched prose that cited that endpoint in order to rule it out. It now only applies to the `ENDPOINT:` line.
- 2026-10-10, development arms for sobre (outside the comparison of released tools): `sobre-dev` (a local build, set up like `sobre`) and `sobre-hooks` (the same build with its hooks only, no MCP server or skill). They bill to the sobre key and are reported beside the other arms; they never replace the `sobre` arm's results.
- 2026-10-10, cost model corrected: cache hits on Sonnet 5.5 cost $0.10 per million tokens (0.05x base input, footnote 2 of the pricing page), not $0.20. Every run of pilots 1 and 2 was re-costed from its stream; the computed cost now matches Claude Code's own estimate. Ratios move by at most 0.03. `harness/prices.json` also gains Haiku 5.5's long-prompt prices (requests over 100K tokens), and `usage.py` sums the `result` events of a multi-turn run.
- 2026-10-10, pilot 3 runs overlap (`bench.py --jobs`), and one agent's `kill` loop over every process matching `pytest` killed two other runs' `claude` and a grading. Since then each turn runs in its own PID namespace (`unshare --pid`), so an agent sees and signals only its own processes, and the prompt goes in on stdin rather than in `claude`'s argv. The affected runs were marked invalid and re-run, and the killed grading was redone. Each server of a parallel run must be UTF8 (`bench.py` checks); runs made on two SQL_ASCII servers before that check were marked invalid and re-run.
