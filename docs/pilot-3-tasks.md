# Pilot 3 tasks: multi-turn conversations

Pilots 1 and 2 put one question to the agent and graded its one answer. Every run succeeded, and the runs were too short for context to pile up. Real agent use is a conversation: the agent investigates, the user asks for a fix, then for a related change, then for a summary, and each message builds on what the agent found before. Pilot 3 measures context tools in that setting. Its tasks are conversations of four user messages on the pilot 2 fixture (`build/pilot2/fixture.git`, plants in `fixture/plants-pilot2.json`).

## How a conversation runs and is graded

- `task.json` holds the first message in `prompt` and the later ones in `followups`. `harness/run.py` sends the first with `claude -p` and each later one with `claude -p --resume <session id>`, as a user typing their next message would. `{DATA_DIR}` works in every message. Each message gets the run's turn and budget limits. The timeout covers the whole conversation. Cost is the sum over all messages.
- Grading happens once, at the end. It looks at the repository as the conversation left it and at the last answer (`answer.md`). `answers.md` keeps every answer, for reading only.
- The grader kind `all` combines a `tests` part (hidden tests copied over the repository, then a regression suite) and a `facts` part (labeled lines of the last answer, matched by regular expressions anchored at line start). A run passes only when both parts pass.
- Later messages depend on earlier ones. A message asks to fix "the bug you found" or asks "which of the commits you listed". The last message asks for a recap that repeats facts found two or three messages earlier: a file, a function, a commit, a date, a list as it stood before the agent's own fixes. An agent that lost those facts must find them again, and in some cases it cannot. Once the code is fixed, the code no longer shows the bug.

## Tasks (`tasks3/`)

| Task | Messages | Grader | Plants | What has to carry across messages |
| --- | --- | --- | --- | --- |
| `mt-reminders-incident` | 1. root cause of missing Monday reminders from 9.7 MB of scheduler and API logs, and the deploy that shipped it; 2. fix it, with a regression test; 3. the nightly TypeError in the same logs: count from the creation time when the triage time is missing; 4. recap | hidden tests (jobs run with a frozen Monday and Tuesday) + `tests/case`; facts: file, function, commit, image tag, first missed Monday, missing field | q4 | The function with the bug after the agent rewrote it, the deploy and dates from the logs, the TypeError's cause |
| `mt-dedup-snooze-regressions` | 1. every commit since 2025-05-22 that changed snooze or deduplication decisions; 2. which of them broke deduplication windows, and fix it; 3. a snooze bug, fix it; 4. recap | hidden tests (window in minutes, expired snooze) + `tests/signal`; facts: two bug commits, the canary commit, the default window and its setting | p1, p4, p5, upstream #6026 | The commit list and the default window from message 1 |
| `mt-security-review` | 1. data-changing case and incident routes without a permission check; 2. which one is a regression: find the commit, restore the check, add a test; 3. members see restricted cases: fix it; 4. recap | original `tests/database` restored + hidden route test, then `tests/case tests/event`; facts: the routes as they were at the start, the restored one, two commits | q5, q1 | The route list before the agent's fix, which a fresh look no longer shows |
| `mt-redaction-entities` | 1. trace a signal instance from the API: masking function, default keys, is the unmasked payload stored; 2. entity extraction keeps only the first match: fix it; 3. unrelated instances grouped into one case: masked values become one shared entity, fix it; 4. recap | original `tests/entity` restored + hidden tests, then `tests/signal`; facts: function, keys, stored unmasked, two commits | p2, q3 | The pipeline facts from message 1, needed again to explain message 3 |

The third message of `mt-redaction-entities` has no plant of its own. Masking runs before entity extraction, so every masked token becomes the same `[REDACTED]` entity. A deduplication filter on that entity type then matches unrelated instances. Finding this needs the facts of messages 1 and 2 together.

No task adds a plant: all four run on the pilot 2 fixture as built. The CI regressions q1 and q3 are fixed within a task, and their original tests are restored before the grader runs them. q2 is left alone, and no task's commands run `tests/case_cost`.

## Check and run

```sh
python3 -I fixture/build.py --spec fixture/plants-pilot2.json --out build/pilot2
python3 -I fixture/gen_logs_pilot2.py build/pilot2
BENCH_DB_PORT=5432 python3 -I tasks/validate.py --fixture build/pilot2/fixture.git --deps-venv "$BENCH_DEPS_VENV" --tasks-dir tasks3
python3 -I harness/bench.py --tasks 'tasks3/*/task.json' --reps 1 --out results/pilot3/raw \
    -- --fixture build/pilot2/fixture.git
```

`tasks/validate.py` checks each part of an `all` grader. For the facts part, `golden.md` must pass and `wrong.md` must fail. For the tests part, the hidden tests must fail on the fixture and pass with `solution.patch`, together with the regression suite. `BENCH_DB_PORT` picks the Postgres server, which Dispatch reads as `DATABASE_PORT`. The fixture's tests create their database as UTF8 from `template1`, so the server's `template1` must be UTF8. `harness/leakage.py` skips these tasks: it only covers single-answer fact tasks, and these recaps ask for commit hashes, log dates and image tags that memory cannot supply.
