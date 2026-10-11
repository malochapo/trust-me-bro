# Pilot 3: a smaller model, conversations, and sobre's compression levels

Pilots 1 and 2 ran one model, Sonnet 5.5, on one-message tasks, and every run succeeded. Pilot 3 asks three questions they could not answer:

1. **Does a smaller model filter its own output less, leaving more for a context tool to save?** Every task runs on Haiku 5.5 as well as Sonnet 5.5, both at effort `medium`.
2. **What happens when context accumulates over a conversation?** Four new tasks are conversations of four user messages ([pilot-3-tasks.md](pilot-3-tasks.md)).
3. **What does sobre's `compression_level` change?** sobre runs at 0.3 (its default), 0.6 and 0.9.

This pilot measures sobre against Claude Code alone. The other tools are not rerun: their pilot 1 and 2 results stand.

## Setup

- **Tasks:** the 10 tasks of pilot 1 (`tasks/`, pilot 1 fixture), the 6 of pilot 2 (`tasks2/`) and the 4 conversations (`tasks3/`), the last two sets on the pilot 2 fixture.
- **Models:** `claude-sonnet-5-5` and `claude-haiku-5-5`, at effort `medium`, through Claude Code 2.1.296. Limits per run: a $3 cap and 25 minutes, the timeout covering a whole conversation.
- **Arms:**
  - `native`: Claude Code alone;
  - `sobre-dev`: a development build of sobre (sobre-ai `cbab75497`) at `compression_level` 0.3, its default;
  - `sobre-dev-06`: the same build at 0.6;
  - `sobre-dev-09`: the same build at 0.9.
  - `sobre-dev-09b`: build `935756b6b` at 0.9. It replaced `sobre-dev-09` after the first runs showed 0.9 cutting a diff short (below).
- **What the build changes:** sobre's post-run hook now folds output by its shape whatever command printed it, so it also works on the chained lines agents write. Each level adds a rule:
  - at every level, runs of one log statement keep their first and last line;
  - from 0.4, consecutive search results of one file print its path once;
  - from 0.8, long output that cannot hold source keeps its first and last lines.
- **Repetitions:** 2 per task, arm and model.
- **Prices:** `harness/prices.json`. Sonnet 5.5 cache hits cost $0.10 per million tokens. Haiku 5.5 costs $0.10 input and $0.50 output per million tokens, with higher prices for a request whose prompt is over 100K tokens.

## Harness changes for this pilot

- **Parallel runs:** `bench.py --jobs N` runs N at a time, each on its own Postgres server. A server must be UTF8, and `bench.py` checks it.
- **Conversations:** a task's `followups` resume the session with `claude -p --resume`.
- **Isolation:** each turn runs in its own PID namespace, and the prompt goes in on stdin. This came after one agent's `kill` loop reached other runs (PROTOCOL.md changelog).
- **Grading:** a grader kind `all` grades a conversation on the repository's final state and on its last answer together.

## Results

(written when the runs end)
