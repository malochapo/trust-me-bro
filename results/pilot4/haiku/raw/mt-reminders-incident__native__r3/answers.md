**Root cause:** the weekly Monday check in `src/dispatch/case/scheduled.py` can never be true, so the close reminders for triage and stable cases are never sent. The daily triage reminders don't use this check, which is why they still arrive.

```python
def _is_reminder_day() -> bool:
    return date.today().isoweekday() == calendar.MONDAY   # line 33
```

`isoweekday()` numbers Monday as 1, but `calendar.MONDAY` is 0 in Python (the `weekday()` convention). I confirmed both values in the sandbox: `calendar.MONDAY` is 0, and `isoweekday()` for a Monday is 1. The comparison is false on every day of the week. Both `case_close_reminder` and `case_stable_reminder` call `_is_reminder_day()`, so both weekly reminders stop.

**Where it was introduced:** commit `c509d45e` ("refactor(case): share the weekly reminder check", Jordan Lee, 2025-08-12). It replaced `date.today().isoweekday() == 1` with `_is_reminder_day()`, which swapped the literal `1` for `calendar.MONDAY`. That swap is the bug. The old code was correct.

**The deploy that shipped it:** `main-81d8ae42` (`fix(case): exclude resolved_by in update`, #6183). It contains `c509d45e`, and the logs show it started on the scheduler and web containers on **2025-08-13 at 16:40 UTC** (`api.log:13201`, `scheduler.log:18851`). Nothing else was deployed in the window.

**How the logs line up:**
- Close reminders were sent on Monday 2025-08-04 (6 sends) and Monday 2025-08-11 (5 sends), both before the deploy.
- On Monday 2025-08-18 the scheduler ran at 18:00 and sent no close reminders.
- Triage reminders kept going out every day after the deploy (for example 08-13 and 08-18).
- The tracebacks for `case_close_reminder` and `case_stable_reminder` changed line numbers at the deploy, consistent with a changed `case/scheduled.py`.

**Two other errors in the same logs, not the cause:**
- `case_close_reminder` (line 47) raises `TypeError` for cases with `triage_at` = None on every run from 08-13 through 08-20. The per-case `try/except` keeps it from stopping the loop, so it doesn't explain the missing sends. It is still a real bug and is worth a follow-up.
- Before the deploy, `case_stable_reminder` raised the same `TypeError` for `stable_at` = None on every run from 07-28. The `if case.stable_at:` guard from `32fa810f` is in `81d8ae42`, and the stable-reminder errors stop after 08-13, so that fix is working.

I haven't changed any code. For the fix, the check should compare against 1 (`date.today().isoweekday() == 1`) or use `date.today().weekday() == calendar.MONDAY`. The next step would be adding a test that pins the reminder day to a Monday.

----- next turn -----

The Monday reminders are fixed, and the new regression tests pass. I haven't committed anything.

**The fix** (`src/dispatch/case/scheduled.py`, line 33): `_is_reminder_day()` now compares `date.today().weekday()` with `calendar.MONDAY`. Before, it compared `isoweekday()` (Monday is 1) with `calendar.MONDAY` (which is 0), so the check was never true.

**The regression tests** (`tests/case/test_case_scheduled.py`, new file):
- `test_is_reminder_day_only_on_monday` checks each day from a Monday through the following Sunday. The Monday case is the one that failed before the fix.
- `test_weekly_reminders_sent_on_monday_only` runs both the close and stable reminder jobs against a case that has been in its status for 8 days. It sends nothing on Tuesday and one reminder on Monday. It uses the real PostgreSQL session fixture and patches the send function. It calls the raw job function, so the test doesn't depend on the scheduler thread pool.

Before the fix, all three failed: the Monday check was false and no Monday reminder was sent. After the fix, all 9 tests in the file pass, and `tests/case` passes (24 tests).

**Full suite:** `python -m pytest` reports 8 failed, 368 passed, 4 skipped. The failures are in `tests/ai/test_ai_service.py`, `tests/database/test_service.py`, and `tests/entity/test_entity_service.py`. They also fail with the fix stashed, so they predate this change. I didn't investigate them.

**Lint:** `ruff check` and `ruff format --check` pass on both changed files.

The `triage_at` / `stable_at` = None `TypeError` in the close-reminder job is still there. It's logged per case but doesn't stop the other cases, so I left it alone.

----- next turn -----

The close reminder no longer throws on cases without a `triage_at` timestamp. Those cases now count from `created_at`, and their weekly reminder goes out on Mondays. I haven't committed.

**What causes the TypeError:** `triage_at` is only written by `case_triage_status_flow`, and that runs only on some transitions. Three paths reach Triage without it:
- **Any other status → Triage** (for example Escalated or Stable → Triage) hits the catch-all branch in `case_status_transition_flow_dispatcher`, which logs a warning and sets nothing.
- **`create()`** stores `case_in.status` directly, so a case created in Triage never gets the timestamp. The signal flow creates cases as New, so that route doesn't explain it.
- **Edits via `service.update()`** also assign status directly. The flow that would set the timestamp runs in a background task after the request, so it can be skipped.

I couldn't confirm which path produced the production rows. The API log doesn't record case IDs, and I have no database access. Any of these paths explains the error.

**The fix** (`src/dispatch/case/scheduled.py`, `case_close_reminder`): the job now computes `triage_start = case.triage_at or case.created_at` and counts from that. The stable reminder is unchanged. It still skips cases without `stable_at`, because the request only covered the close reminder.

**The test** (`tests/case/test_case_scheduled.py`): `test_close_reminder_counts_from_created_at_without_triage_at` covers a triage case with `triage_at = None`, run on a Monday:
- Created 8 days ago: a reminder is sent.
- Created 2 days ago: no reminder is sent.

Without the fallback, the 8-day case raises the same TypeError inside the per-case `try`, so nothing is sent and the test fails.

**Verification:** all 11 tests in the scheduled test file pass, and `tests/case` passes (26 tests). Ruff check and format pass on both files. I didn't re-run the full suite. The 8 failures in `tests/ai`, `tests/database`, and `tests/entity` from earlier are unrelated and still there.

----- next turn -----

Recap of the reminder incident and the two fixes:

- **Symptom:** Since mid-August, assignees stopped getting the Monday reminders to close long-running triage and stable cases. Daily triage reminders kept going out.
- **Root cause:** `_is_reminder_day()` in `src/dispatch/case/scheduled.py` compared `date.today().isoweekday()` (Monday = 1) with `calendar.MONDAY` (Monday = 0). The check was never true, so both weekly reminder jobs sent nothing.
- **How it shipped:** `c509d45e` ("refactor(case): share the weekly reminder check", 2025-08-12) introduced the check. It reached production in `main-81d8ae42`, which started on the web and scheduler containers at 2025-08-13 16:40 UTC. The last Monday with sends was 2025-08-11, before the deploy. The first missed Monday was 2025-08-18.
- **Fix:** `_is_reminder_day()` now uses `date.today().weekday() == calendar.MONDAY`. The regression tests in `tests/case/test_case_scheduled.py` fail on the old code and pass on the fix.
- **Evening TypeError:** The close reminder subtracted `case.triage_at` from `utcnow()`. Cases that reached triage without that timestamp raised a TypeError, which the per-case `try` caught and logged. The paths that skip `triage_at` are: transitions into Triage from Escalated or Stable, cases created directly in Triage, and status edits through `service.update()`. I couldn't confirm which one produced the production rows, because the logs don't record case IDs. The job now counts from `created_at` when `triage_at` is missing, and a test covers that.
- **Still open:** The stable reminder still skips cases without `stable_at` and does not fall back to a timestamp. The 8 failures in `tests/ai`, `tests/database`, and `tests/entity` predate these changes and are unrelated.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e97f4eeacf950450c142ee27da8fcda3f
DEPLOYED_IMAGE: main-81d8ae42
FIRST_MISSED: 2025-08-18
MISSING_FIELD: triage_at