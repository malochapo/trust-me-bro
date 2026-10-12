**Root cause:** the weekly Monday check in `src/dispatch/case/scheduled.py` never matches, so the close and stable reminders are never sent on any day.

Commit `c509d45e` (Jordan Lee, 2025-08-12, "refactor(case): share the weekly reminder check") moved the Monday test into a helper:

```python
def _is_reminder_day() -> bool:
    return date.today().isoweekday() == calendar.MONDAY
```

`calendar.MONDAY` is `0` in Python (I checked: `calendar.MONDAY = 0`), but `isoweekday()` returns `1` for Monday. The comparison is therefore always false. The old inline code compared against the literal `1`, which was correct. The refactor changed behavior with no test to catch it.

**Deploy that shipped it:** image `registry.example.com/dispatch:main-81d8ae42`, started on the scheduler at 2025-08-13 16:40 UTC (and the web container at the same time). `81d8ae42` is a commit from 2025-08-12, and `c509d45e` is an ancestor of it. The previous image, `main-b05613b5`, was deployed 2025-07-30 and predates the refactor.

**Logs confirm it:**
- Monday 2025-08-11 (before the deploy): 5 "Case close reminder sent" entries and no stable-reminder sends. Those were the last weekly reminders.
- Monday 2025-08-18 (first Monday after the deploy): the case close and stable jobs ran, but there are zero reminder sends.
- Daily triage reminders kept running on every day, because `case_triage_reminder` doesn't use the Monday check.

**Secondary issue (separate, not the cause):**
- `case_stable_reminder` was throwing `datetime - NoneType` on every run from 2025-07-28 because some stable cases have no `stable_at`. `32fa810f` (2025-08-11, "fix(scheduler): not all cases have a stable_at date") added a `if case.stable_at:` guard, and the errors stop after 2025-08-12.
- `case_close_reminder` now logs the same kind of error from 2025-08-10 onward, for cases with a null `triage_at`. These are caught per case, so they only skip those cases. It's worth a follow-up, but it doesn't explain the Monday drop.

**Fix (not applied):** change `_is_reminder_day()` to compare against `1` or use `date.today().weekday() == calendar.MONDAY`. `weekday()` is the 0-based form and matches `calendar.MONDAY`. A test that pins a Monday date would catch this in the future.

I didn't change any code.

----- next turn -----

The Monday reminder bug is fixed and a regression test covers it. The new tests and the existing case tests pass under `python -m pytest`, run against the local PostgreSQL.

**The fix** (`src/dispatch/case/scheduled.py`): `_is_reminder_day()` now uses `date.today().weekday()`, which is 0-based like `calendar.MONDAY`. The old `isoweekday()` is 1-based, so the comparison never matched.

**The regression tests** (new file `tests/case/test_case_scheduled.py`, 10 tests):
- `test_is_reminder_day` checks Monday through Sunday of a week with a frozen date.
- `test_weekly_reminders_sent_on_monday_only` runs the real close and stable reminder jobs, with the case lookup and send stubbed. It expects a send on Monday and none on Tuesday.
- `test_stable_reminder_skips_cases_without_stable_at` covers the `stable_at` guard from the earlier fix.

To check that the tests catch the bug, I temporarily restored `isoweekday()`. Three tests failed, and I then restored the fix.

**Other results:**
- `tests/case` runs 25 passed.
- `ruff check` passes on both changed files.
- `ruff format` reformatted the new test file. That is the only change to it after I wrote it.

Nothing is committed. The diff is one line in `scheduled.py` plus the new test file. Once this ships, the next Monday run should send the close and stable reminders again.

----- next turn -----

The close reminder now counts from `created_at` when `triage_at` is missing, and there's a regression test for it. The case tests pass under `python -m pytest` (28 total, including the new ones).

**What causes the TypeError:** `case_close_reminder` does `datetime.utcnow() - case.triage_at`, and some triage cases have `triage_at = NULL`. Python raises `TypeError: unsupported operand type(s) for -: 'datetime.datetime' and 'NoneType'`. The per-case `try/except` catches it and logs it, so the other cases still get processed, but the case with the null timestamp never gets its reminder. The errors appear every evening from 2025-08-10, and the same error shows up in the Monday runs too.

**Why cases end up with `triage_at = NULL`:** `triage_at` is only set by `case_triage_status_flow`. Several paths put a case into triage without running that flow:
- `service.create` sets `status` directly, so a case created with status triage never gets a `triage_at`.
- The fallback `(_, CaseStatus.triage)` branch in `case/flows.py` logs a warning and doesn't set `triage_at`.
- `reopen_button_click` in `plugins/dispatch_slack/case/interactive.py` (around line 1427) assigns `case.status = CaseStatus.triage` without calling the flow.

The logs don't name the affected cases, so I can't say which of these caused the production rows. To check, run `SELECT id, created_at FROM "case" WHERE status = 'triage' AND triage_at IS NULL;` against production. I didn't change any of those paths, since the request was about the reminder job.

**The fix** (`src/dispatch/case/scheduled.py`): the job now uses `triage_start = case.triage_at or case.created_at`. `created_at` is already loaded by `get_all_by_status`. `triage_at` still wins whenever it is set.

**The tests** (`tests/case/test_case_scheduled.py`): a parametrized test runs the real close-reminder job on a Monday, with the lookup and send stubbed. It covers three cases:
- No `triage_at`, created 14 days ago: reminder sent.
- No `triage_at`, created 2 days ago: not sent.
- `triage_at` 2 days ago, created 30 days ago: not sent, because `triage_at` takes precedence.

Under the old code, the first case would raise inside the `try`, get swallowed, and not send, so that test fails there.

Nothing is committed. The stable reminder already skips cases with no `stable_at`, so I left it as is.

----- next turn -----

**Recap**

- **Weekday bug:** `_is_reminder_day()` in `src/dispatch/case/scheduled.py` compared `date.today().isoweekday()` (Monday = 1) against `calendar.MONDAY` (Monday = 0). The comparison was never true, so the weekly close and stable reminders never went out. The triage reminders are daily and don't use this check, so they were unaffected.
- **Introduced by:** commit `c509d45e` (2025-08-12, "refactor(case): share the weekly reminder check"). It replaced an inline check that compared against the literal `1`, which was correct.
- **Shipped:** image `registry.example.com/dispatch:main-81d8ae42`, started on the scheduler at 2025-08-13 16:40 UTC. The previous image, `main-b05613b5`, predates the refactor.
- **Impact:** the Monday 2025-08-11 run, before the deploy, sent its reminders. The first Monday missed was 2025-08-18, and the job ran that day with zero close or stable sends.
- **Fix and tests:** `weekday()` replaces `isoweekday()`. The new tests in `tests/case/test_case_scheduled.py` fail with the bug restored and pass with the fix.
- **Evening TypeError:** `case_close_reminder` subtracted `case.triage_at`, which is `NULL` for some cases in triage. The error is caught per case, so those cases were skipped and never got their reminder. I changed the job to count from `case.created_at` when `triage_at` is missing. The exact path that leaves `triage_at` empty isn't confirmed; the logs don't name the cases.
- **Not committed:** all changes are in the working tree.

```
FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e
DEPLOYED_IMAGE: main-81d8ae42
FIRST_MISSED: 2025-08-18
MISSING_FIELD: triage_at
```