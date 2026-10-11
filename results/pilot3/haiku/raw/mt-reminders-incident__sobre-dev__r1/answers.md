**Root cause:** `_is_reminder_day()` in `src/dispatch/case/scheduled.py:31-33` compares the wrong weekday numbering. Python's `calendar.MONDAY` is `0`, while `date.today().isoweekday()` returns `1` for Monday. The check is `isoweekday() == calendar.MONDAY`, which is `1 == 0`, so it is never true. The weekly close and stable reminders therefore never fire. I confirmed this with `python3 -I`: `calendar.MONDAY = 0`, and Monday 2025-08-18 has `isoweekday() = 1`, so the match is `False`.

**Commit that introduced it:** `c509d45e` "refactor(case): share the weekly reminder check" (Jordan Lee, 2025-08-12). The original code was `date.today().isoweekday() == 1`, which was correct. The refactor moved it into `_is_reminder_day()` and changed the constant to `calendar.MONDAY`. Both `case_close_reminder` and `case_stable_reminder` call the helper, so both reminders stopped. The triage reminder doesn't use it, which is why daily triage reminders still arrive.

**Deploy that shipped it:** Image `registry.example.com/dispatch:main-81d8ae42`, started on the scheduler and web pods at 2025-08-13 16:40 UTC (`scheduler.log:18851`, `api.log:13201`). `81d8ae42` is "fix(case): exclude resolved_by in update (#6183)", and `c509d45e` is its ancestor, so the refactor rode along with an unrelated fix. The previous image, `main-b05613b5`, was deployed 2025-07-30 and does not contain `c509d45e`.

**Timeline in the logs:**
- Close reminders were sent on Mondays 2025-07-28, 08-04 and 08-11.
- The first missed Monday is 2025-08-18. No "Case close reminder sent" lines appear after 08-11.
- The traceback line numbers shift from 43/51 to 47/55 after the deploy, which matches the four lines the refactor added.

**Unrelated noise:** Both `case_close_reminder` and `case_stable_reminder` log a `datetime - NoneType` error on every daily run from 2025-07-28 onward. The `triage_at` / `stable_at` value is `None` for some cases. The per-case `try/except` swallows these, so they don't block other cases, and they predate the regression. They are worth a separate look but are not the cause.

**Suggested fix (not applied):** compare against `0` or use `date.today().weekday() == calendar.MONDAY`. Rolling back `main-81d8ae42` would also stop the bug, but the commit `c509d45e` is still in the tree. The fix needs a test that pins Monday to the right value.

No code has been changed, and the working tree is clean.

----- next turn -----

The weekly reminders are fixed, and a regression test covers the bug. I haven't committed anything.

**The fix** (`src/dispatch/case/scheduled.py:34`): `_is_reminder_day()` now uses `date.today().weekday() == calendar.MONDAY`. Both sides use Monday = 0. The old `isoweekday()` returns Monday = 1, which never matched `calendar.MONDAY` (0).

**The regression test** (`tests/case/test_case_scheduled.py`, new file): it fakes `date.today()` and checks `_is_reminder_day()` for each day from Monday 2025-08-11 to Sunday 2025-08-17. It passes with the fix. I temporarily put the old `isoweekday()` line back, and the Monday case failed (`1 failed, 6 passed`), then I restored the fix.

**Test results** (`python -m pytest`, PostgreSQL running locally):
- `tests/case/test_case_scheduled.py`: 7 passed
- `tests/case` (whole directory): 22 passed

I didn't run the full test suite, only the case directory.

The weekly reminders should go out again on the next Monday after this change is deployed. The per-case `None` timestamp errors from earlier are still there. They are caught per case and don't stop the other cases, so I left them alone.

----- next turn -----

The close reminder no longer crashes on missing `triage_at`. Cases with no `triage_at` now count from `created_at`, and the regression test covers it.

**What causes the TypeError:** `triage_at` is written only by `case_triage_status_flow` (`src/dispatch/case/flows.py:592`). Any case that reaches Triage without running that flow keeps `triage_at = NULL`, and then `datetime.utcnow() - None` raises. The paths I found that skip it:
- `reopen_button_click` (`src/dispatch/plugins/dispatch_slack/case/interactive.py:1427`) sets `case.status = CaseStatus.triage` directly.
- Cases created in Triage through the API rely on a background task (`case_triage_create_flow`) to set `triage_at`. If that task fails, the timestamp stays empty.

The logs don't include case IDs, so I can't say which of these produced the affected production rows. The reopen path is the most direct match. The per-case `try/except` catches the error, which is why the job still sends the other cases' reminders.

**The fix** (`src/dispatch/case/scheduled.py:47-50`): `started_at = case.triage_at or case.created_at`, and the span is measured from `started_at`.

**The test** (`tests/case/test_case_scheduled.py`): `test_case_close_reminder_falls_back_to_created_at` creates two Triage cases with no `triage_at`, one created 8 days ago and one created today. On a faked Monday, it checks that only the old case gets a reminder. The test calls the real job by looking it up in `scheduler.registered_tasks`, because the `@scheduler.add` decorator returns `None`.
- With the fix: the test passes.
- Without the fix: the test fails, as expected.

**Results:** all 8 tests in `test_case_scheduled.py` pass, and all 23 tests in `tests/case` pass against the local PostgreSQL.

**Things to know:**
- The `CaseFactory` ignores a `status=` argument because of its `class Params` block. The test sets `status` after creating the cases instead.
- For the last few runs I added `-p no:schemathesis` to suppress a plugin traceback. The first run without it also passed.
- I didn't change the stable reminder. It still skips cases with no `stable_at` and never falls back to `created_at`, unlike the close reminder. Tell me if you want the same fallback there.
- I didn't fix the underlying flow gap (the reopen path and background-task failures). That would be a separate change to `reopen_button_click` and the create-in-triage path.

The earlier weekday fix and this change are both uncommitted in the working tree, along with the new test file.

----- next turn -----

**Recap**

- **Weekly reminders stopped.** The check in `_is_reminder_day()` compared `date.today().isoweekday()` (Monday = 1) with `calendar.MONDAY` (Monday = 0). It was never true, so the weekly close and stable reminders never sent. Commit `c509d45e` introduced the bug in a refactor. Image `main-81d8ae42` shipped it to the scheduler and web pods on 2025-08-13 at 16:40 UTC. The last Monday with sends was 2025-08-11, and the first missed was 2025-08-18.
- **Evening TypeError.** The close-reminder job subtracted `case.triage_at` from the current time. `triage_at` is only set by the triage transition flow, so cases that reached Triage another way (for example, the Slack reopen handler, or a create-in-triage background task that failed) had it empty. The job now counts from `created_at` in that case. The per-case error handling meant other cases still got their reminders.
- **Fix and tests.** The weekday check now uses `date.today().weekday()`. The close job falls back to `created_at`. The new tests in `tests/case/test_case_scheduled.py` fail on the old code and pass on the fix. All 23 tests in `tests/case` pass against the local PostgreSQL.
- **Not yet done.** Both changes are uncommitted and not deployed. The stable reminder still skips cases with no `stable_at`. The logs don't name the affected cases, so I can't confirm which path produced them.

```
FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e97f4eeacf950450c142ee27da8fcda3f
DEPLOYED_IMAGE: main-81d8ae42
FIRST_MISSED: 2025-08-18
MISSING_FIELD: triage_at
```