**Root cause:** the weekday check in `_is_reminder_day()` compares `isoweekday()` (Monday = 1) against `calendar.MONDAY`, which is 0 in Python. The check can never be true, so both Monday reminders (triage-close and stable) are silently skipped. The daily triage reminders use a different function without this check, which is why they still arrive.

**Introduced by:** commit `c509d45e` (Jordan Lee, 2025-08-12, "refactor(case): share the weekly reminder check"). It replaced `date.today().isoweekday() == 1` with `_is_reminder_day()`, which compares against `calendar.MONDAY`. The old literal `1` was correct, so the refactor changed behavior. It's in `src/dispatch/case/scheduled.py:31-33`, and the two call sites are at lines 49 and 95.

**Deploy that shipped it:** image `main-81d8ae42`, which is commit `81d8ae42` (David Whittaker, "fix(case): exclude resolved_by in update (#6183)", 2025-08-12 14:47 PDT). It includes `c509d45e` in the range `b05613b5..81d8ae42`. The scheduler pod restarted on that image at 2025-08-13 16:40 UTC (`scheduler-mhtsgqwwx-q5q2n`). The image tag matches the commit short SHA, which I assumed rather than confirmed from the registry.

**Evidence from the logs:**
- Reminder sends happened on Mondays 2025-07-28 (4), 08-04 (6) and 08-11 (5), all on the old scheduler pod.
- The Monday 2025-08-18 run sent no close reminders. The only close-reminder entry is a `TypeError` from the triage path.
- `calendar.MONDAY` is 0, and `isoweekday()` for 2025-08-18 is 1, so the comparison is False.
- The API log has no reminder entries, so it doesn't add to the diagnosis.

**Secondary issue (not the cause):** `case_close_reminder` still computes `datetime.utcnow() - case.triage_at` with no `None` guard. Commit `32fa810f` added the guard only to the stable path. Since 08-13, the triage path logs a `TypeError` every day for a case with no `triage_at`. The per-case try/except keeps other cases going, so this doesn't block the Monday sends.

I haven't changed any code. When you're ready for the fix, the minimal change is to compare against `1` (or `calendar.MONDAY + 1`), and to add the `triage_at` guard on the triage path. I'd also add a test that runs the reminder on a Monday.

----- next turn -----

The Monday reminders now go out again, and a regression test covers the bug. I haven't committed anything.

**The fix** (`src/dispatch/case/scheduled.py`)
- `_is_reminder_day()` compared `isoweekday()` (Monday = 1) to `calendar.MONDAY` (= 0), so it was never true. It now uses `date.today().weekday()`, which is 0-based like `calendar.MONDAY`.
- I also added the `if case.triage_at:` guard to `case_close_reminder`, matching the guard the stable path already has. Without it, a triage case with no `triage_at` raised a `TypeError` on every daily run. The per-case `try` kept other cases running, but the error was still logged each day. This goes beyond the Monday bug, so you may want to drop it from the change.

**The regression test** (`tests/case/test_case_scheduled.py`, new)
- It runs both the triage-close and stable reminder tasks on each day of one week, with a case that has been waiting 10 days. A reminder should be sent only on Monday.
- It also checks that a case with no timestamp doesn't stop a valid case from being reminded.
- The tests call the undecorated task function, and they patch `date` in the module to control the day. The scheduler decorator doesn't return the function, so the tests look it up in `scheduler.registered_tasks`.
- The factory ignores a `status` keyword because `CaseFactory` declares `status` as a `Params` entry, so the test sets the status after creating the case.

**Verification**
- `python -m pytest tests/case/test_case_scheduled.py`: 16 passed.
- With the original weekday line restored, 4 tests fail: the Monday cases for both tasks and the no-timestamp case. I restored the fix afterwards.
- `python -m pytest tests/case`: 31 passed.
- `ruff check` and `ruff format --check` pass on both changed files.

I didn't run the full test suite, and I didn't check the change against the live scheduler, so the first real confirmation will be the next Monday run in production.

----- next turn -----

The evening TypeError came from triage cases with no `triage_at`. The reminder now counts those from `created_at` instead, and a regression test covers it. I haven't committed anything.

**What causes it**
- `triage_at` is set only in `case_triage_status_flow` (`src/dispatch/case/flows.py:592`), which runs on the New→Triage and Closed→Triage transitions.
- A case that is created directly in Triage never runs that flow. `service.create` writes `case_in.status` straight to the row (`src/dispatch/case/service.py:205`), and `CaseCreate` accepts a status.
- Stable→Triage and Escalated→Triage fall into the `(_, Triage)` branch of the dispatcher, which logs a warning and skips the flow. Those cases also never get `triage_at` if they never went through New→Triage.
- `case_close_reminder` then does `datetime.utcnow() - None`. The per-case `try` logs it and moves on, so the Monday send was not blocked by this error, but the error still fired every night.

**The fix** (`src/dispatch/case/scheduled.py`)
- The reminder now computes `datetime.utcnow() - (case.triage_at or case.created_at)`. This replaces the `if case.triage_at:` guard I added last turn. The triage path's behavior now matches what you asked for.
- I left the stable path alone. Cases with no `stable_at` are still skipped there, not counted from creation, since you only asked about triage. Say if you want that changed too.

**The test** (`tests/case/test_case_scheduled.py`)
- `test_triage_case_without_triage_at_counts_from_created_at` creates two triage cases with no `triage_at`. One was created 10 days ago and one 2 days ago. On a Monday, only the 10-day-old case should be reminded.
- With the fix the test passes. With the old `triage_at`-only line restored it fails, so the test catches the regression.

**Verification**
- `python -m pytest tests/case`: 32 passed.
- `ruff check` and `ruff format --check` pass on both changed files.

**Not fixed, but worth a follow-up**
- Creating a case directly in Triage, or moving one from Stable or Escalated into Triage, never sets `triage_at`. Setting it in the create path and in the `(_, Triage)` branch would stop the fallback from being the normal path.

----- next turn -----

Here is the recap for the incident report. I haven't changed any code since the last fix, and the six lines at the end are the values you asked for.

**Summary**

- **Symptom:** assignees stopped getting the Monday reminders to close long-running triage and stable cases. The daily triage reminders kept arriving, and nobody changed the settings.
- **Root cause:** in `_is_reminder_day()`, the weekday check compared `date.today().isoweekday()` (Monday = 1) against `calendar.MONDAY` (Monday = 0). The check was never true, so both Monday jobs silently skipped every case.
- **How it was introduced:** commit `c509d45e` (Jordan Lee, 2025-08-12, "refactor(case): share the weekly reminder check") moved the check into the helper and used `calendar.MONDAY`. The old literal `1` was correct.
- **Deploy:** the scheduler restarted on image `main-81d8ae42` at 2025-08-13 16:40 UTC, and the Monday 2025-08-18 run was the first to skip sends. I'm inferring that the tag matches commit `81d8ae42` from the naming; I didn't check the registry.
- **Evidence:** Monday runs on 07-28, 08-04 and 08-11 sent close reminders. The 08-18 run sent none.
- **Fix:** `weekday() == calendar.MONDAY`. I've also changed the triage path to count from `created_at` when `triage_at` is missing. Regression tests are in `tests/case/test_case_scheduled.py`. The 17 tests in that file pass, and the 32 in `tests/case` pass.

**Secondary issue:** the evening TypeError came from triage cases with no `triage_at`. `triage_at` is set only in `case_triage_status_flow`, which runs on New→Triage and Closed→Triage. A case created directly in Triage, or moved from Stable or Escalated into Triage, never gets it. The Monday send wasn't blocked by this, since the per-case `try` caught the error, but it logged every night.

**Still open:**

- Stable cases with no `stable_at` are still skipped rather than counted from creation. I only changed the triage path.
- Setting `triage_at` in `service.create` and in the `(_, Triage)` branch would address the root of the secondary issue.

```
FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e97f4eeacf950450c142ee27da8fcda3f
DEPLOYED_IMAGE: main-81d8ae42
FIRST_MISSED: 2025-08-18
MISSING_FIELD: triage_at
```