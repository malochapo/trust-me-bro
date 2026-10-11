**Root cause:** commit `c509d45e` ("refactor(case): share the weekly reminder check", Jordan Lee, 2025-08-12) replaced the Monday check with a helper that compares the wrong constants:

```python
# src/dispatch/case/scheduled.py
def _is_reminder_day() -> bool:
    return date.today().isoweekday() == calendar.MONDAY
```

`isoweekday()` numbers Monday as 1, but `calendar.MONDAY` is 0 (`calendar` numbers Monday as 0, `isoweekday()` numbers it as 1). I checked both in Python: `calendar.MONDAY = 0`, and `isoweekday()` for 2025-08-18 (a Monday) is 1. So `_is_reminder_day()` is never true, on any day of the week.

The old code was `date.today().isoweekday() == 1`, which was correct. The refactor changed that line as part of the extraction.

**Why only the weekly reminders stopped:** `_is_reminder_day()` gates only the weekly paths:
- `case_close_reminder` (long-running triage cases), and
- `case_stable_reminder` (stable cases).

`case_triage_reminder` has no weekday check, so the daily triage reminders keep going out, which matches what you're seeing.

**Evidence in the logs:**
- The last `Case close reminder sent` lines are on 2025-08-11 (a Monday, before the change). Monday 2025-08-18 has none, and the scheduler log runs through 2025-08-20.
- `Case triage reminder sent` continues after 08-13.

**The deploy that shipped it:** image `registry.example.com/dispatch:main-81d8ae42`.
- The scheduler started on that image at 2025-08-13T16:40:06Z, and the web pods at 16:40:07Z (`scheduler.log:18851`, `api.log:13201`).
- `c509d45e` is an ancestor of `81d8ae42`, and it is not in the previous image `main-b05613b5`.
- `81d8ae42` is the HEAD commit at build time, so `main-81d8ae42` is the build of that commit. That tag-to-commit mapping is my inference from the tag format; I didn't check the registry or deploy config.

**Two things that are not the cause:**
- Between 2025-07-28 and 2025-08-11, `case_stable_reminder` raised `TypeError` on cases with `stable_at = NULL`. That was a separate bug, fixed by `32fa810f` on 08-11. It doesn't explain the mid-August change.
- The reminder settings were not changed, as you said.

No code has been changed. A fix would make the weekday check compare like with like: either `isoweekday() == 1`, or `date.today().weekday() == calendar.MONDAY`. Tell me if you want that applied.

----- next turn -----

The weekly reminders are fixed and there is a regression test for them. I haven't committed anything.

**The fix** (`src/dispatch/case/scheduled.py:33`): `_is_reminder_day()` compared `date.today().isoweekday()` (Monday = 1) with `calendar.MONDAY` (Monday = 0). It now uses `date.today().weekday()`, which uses the same numbering as `calendar.MONDAY`.

**The regression test** (`tests/case/test_case_scheduled.py`, new): it pins `date.today()` to each day of the week and checks `_is_reminder_day()`. Monday must return True and the other six days False.
- On the fixed code, all 7 cases pass.
- On the old `isoweekday()` line, the Monday case fails and the other six pass, so the test catches the bug.

**Test results** (`python -m pytest`):
- `tests/case`: 22 passed.
- Full suite: 366 passed, 4 skipped, 8 failed. The 8 failures are in `tests/ai/test_ai_service.py`, `tests/database/test_service.py::test_restricted_case_filter_with_test_data` and `tests/entity/test_entity_service.py::test_find_entities_with_field_only`. I ran those three files with my change stashed and the same 8 failed, so they predate this work. I didn't investigate their causes.

----- next turn -----

The close reminder now counts from `created_at` when `triage_at` is missing, and there are tests for it. Those cases get their weekly reminder again.

**Cause:** `case_close_reminder` does `datetime.utcnow() - case.triage_at`, and some cases in Triage have `triage_at = NULL`. Subtracting `None` raises the `TypeError`. The per-case `try/except` catches it and logs it, so one bad case is skipped and the job still runs. The same pattern in `case_stable_reminder` was fixed earlier by 32fa810f, which skips cases with no `stable_at`.

I could not confirm which cases these are. `triage_at` is written in only one place, `case_triage_status_flow` (`src/dispatch/case/flows.py:592`). Two paths could leave a Triage case without it:
- The `(_, CaseStatus.triage)` branch in `case_status_transition` (around `flows.py:766`) logs a warning and does not set `triage_at`. Cases that move into Triage from Stable, for example, can end up here. The logs contain no such warnings, but the scheduler may not log at that level.
- Cases in Triage from before the `triage_at` column was added in 2022 (`391f7c3e6992`), which may never have been backfilled.

To confirm which path it is, run this against the tenant schema in production (I have no access to it from here):
`SELECT id, created_at, status FROM "case" WHERE status = 'Triage' AND triage_at IS NULL;`

**Changes:**
- `src/dispatch/case/scheduled.py`: `span = datetime.utcnow() - (case.triage_at or case.created_at)`, with a comment explaining the fallback.
- `tests/case/test_case_scheduled.py`: three new tests, which run the real job through the scheduler's registered task:
  - a case with `triage_at` 8 days old gets a reminder,
  - a case with no `triage_at` and `created_at` 8 days old gets a reminder,
  - a case with no `triage_at` and `created_at` 2 days old gets none.

  The fallback test fails when the fallback is removed, as expected.

**Test results:** `python -m pytest`: 369 passed, 4 skipped, 8 failed. The 8 failures are the same ones as before my changes (`tests/ai/test_ai_service.py`, `tests/database/test_service.py::test_restricted_case_filter_with_test_data`, `tests/entity/test_entity_service.py::test_find_entities_with_field_only`).

**Not changed:**
- The stable reminder still skips cases with no `stable_at`. You asked about the close job only; say if you want the same fallback there.
- Nothing is committed.

----- next turn -----

Recap for the incident report:

**Weekly case reminders stopped after the 2025-08-13 deploy.** Monday reminders for long-running triage and stable cases were never sent again. Daily triage reminders kept going out.

- **Cause:** Commit `c509d45e` (2025-08-12, "refactor(case): share the weekly reminder check") moved the Monday check into `_is_reminder_day()`. The new code compared `date.today().isoweekday()` (Monday = 1) with `calendar.MONDAY` (Monday = 0), so it was never true.
- **Fix:** `_is_reminder_day()` now uses `date.today().weekday()`. A regression test (`tests/case/test_case_scheduled.py`) checks each day of the week and fails on the old line.
- **Deploy:** Image `main-81d8ae42` started on the scheduler at 2025-08-13T16:40:06Z. It contains `c509d45e`, and `main-b05613b5`, which ran before it, does not. I inferred the tag-to-commit mapping from the tag format and did not check the registry.
- **Impact:** The last close reminders went out on Monday 2025-08-11. Monday 2025-08-18 was the first missed weekly run, and the logs show no close reminders that day.

**Separate nightly TypeError in the close reminder job.** Cases in Triage with a NULL `triage_at` made `datetime.utcnow() - case.triage_at` raise. The per-case `try/except` logged it and skipped the case, so those cases never got a weekly reminder.
- **Fix:** The job counts from `case.triage_at or case.created_at`. Three tests cover it, and the fallback test fails without the fix.
- **Open:** I could not identify which cases have a NULL `triage_at`, and the cause is unconfirmed. Either the transition path into Triage skips setting it (`case_status_transition`'s `(_, CaseStatus.triage)` branch), or older cases were never backfilled when the column was added in 2022. Checking production for `status = 'Triage' AND triage_at IS NULL` would settle it.

**Test suite:** 369 passed, 4 skipped, 8 failed. The 8 failures are in `tests/ai/test_ai_service.py`, `tests/database/test_service.py`, and `tests/entity/test_entity_service.py`, and they fail the same way without my changes.

**Not done:** Nothing is committed. The stable reminder still skips cases with no `stable_at`, which you did not ask me to change.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e97f4eeacf950450c142ee27da8fcda3f
DEPLOYED_IMAGE: main-81d8ae42
FIRST_MISSED: 2025-08-18
MISSING_FIELD: triage_at