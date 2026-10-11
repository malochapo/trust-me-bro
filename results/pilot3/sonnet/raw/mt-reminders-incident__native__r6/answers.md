**Root cause:** commit `c509d45e` ("refactor(case): share the weekly reminder check", Jordan Lee, 2025-08-12) broke the Monday check. It replaced `date.today().isoweekday() == 1` with a new helper, `_is_reminder_day()`, in `src/dispatch/case/scheduled.py:31-33`. The helper does `date.today().isoweekday() == calendar.MONDAY`. `calendar.MONDAY` is `0`, but `isoweekday()` returns 1 to 7, with Monday as 1. The comparison is never true, so `case_close_reminder` and `case_stable_reminder` (the long-running triage and stable reminders) silently skip every case, every day. I confirmed in Python that `calendar.MONDAY` is 0 and that 2025-08-18 has `isoweekday()` 1. Nothing is logged, because the condition is simply false, and the settings were never involved. The daily `case_triage_reminder` doesn't use this helper, which is why those still arrive.

**Deploy that shipped it:** the production image changed from `main-b05613b5` to `main-81d8ae42` on 2025-08-13 at about 16:40Z. The web pod's kubelet line in `api.log` shows the image tag, and the scheduler pod was replaced at the same moment. `81d8ae42` is the first deployed commit that contains `c509d45e`. The previous image, `b05613b5`, did not. The same deploy also carried `32fa810f` (the `stable_at` null-guard), `bce2fca2` and `92f13c0a`, but they don't affect the Monday check.

**Evidence from the logs:**
- Case close reminders went out on Mondays 07-28 (4 sent), 08-04 (7) and 08-11 (6), the last on the old build.
- On Monday 08-18 at 18:00Z, on the new scheduler pod `scheduler-mhtsgqwwx-q5q2n`, `case_stable_reminder` ran in 0.03s with no error and sent nothing. `case_close_reminder` also sent nothing, because it hit the separate error below. The triage reminder and the incident close reminder still sent.
- The first Monday after the deploy is the first missed one, which matches "since mid-August".

**Separate pre-existing bug, not the cause:** `case_close_reminder` logs `datetime - None` (`case.triage_at` is None) every day, before and after the deploy. That error happens before the Monday check, so on the cases that hit it, it would block the reminder even once the check is fixed. On the cases affected, `triage_at` is None, so the subtraction fails and the reminder is skipped. `32fa810f` added a `stable_at` guard to the stable reminder, but there is no equivalent guard for `triage_at`. I'd fix both together.

**Suggested fix (not applied, as you asked):** compare against `calendar.MONDAY + 1`, or better `date.today().weekday() == calendar.MONDAY`. Also add a test that mocks a Monday date and asserts the reminder is sent, and guard `triage_at` the same way `stable_at` is guarded.

----- next turn -----

Fixed, and the new tests fail on the old code and pass on the fix. I ran only the new test file (`python -m pytest tests/case/test_case_scheduled.py`: 11 passed), not the full suite. Nothing is committed.

**Fix** (`src/dispatch/case/scheduled.py`):
- `_is_reminder_day()` now uses `date.today().weekday() == calendar.MONDAY`. `weekday()` counts Monday as 0, which matches `calendar.MONDAY`; `isoweekday()` counts it as 1, so the old check never matched.
- `case_close_reminder` now skips cases where `triage_at` is None, the same way `case_stable_reminder` already skips a missing `stable_at`. Without this, a case with no `triage_at` makes the `datetime - None` subtraction raise, so that case never gets a reminder. The error was logged every day in your scheduler log. It wasn't the cause of the missing Monday reminders, but it would have kept blocking `case_close_reminder` for those cases after the main fix.

**Regression test** (`tests/case/test_case_scheduled.py`):
- It pins "today" and runs both real scheduled tasks against fake cases.
- It checks that a reminder is sent on a Monday for a case older than a week.
- It checks that nothing is sent on Sunday or Tuesday, or for a case under a week old.
- It checks that a case with a missing timestamp doesn't stop the other cases from being reminded.
- A separate test covers `_is_reminder_day()` on each day of the week.

With only the source fix reverted, 5 of the 11 tests fail: the Monday-sends cases, the missing-timestamp cases and the weekday test.

The pinned-date tests don't need PostgreSQL, so they don't exercise the database path.

----- next turn -----

The TypeError comes from `case.triage_at` being None, and cases in that state now get their weekly reminder, counted from creation. `python -m pytest tests/case` passes (29 tests). Nothing is committed.

**Cause:** `case_close_reminder` runs `datetime.utcnow() - case.triage_at` for every case in triage status. `triage_at` is only set by `case_triage_status_flow` in `src/dispatch/case/flows.py`, when a case goes through a status transition. A case that is in triage but never went through that flow has no `triage_at`, so the subtraction fails. The exception is caught and logged per case, so it fills the log every evening and the case never gets its reminder. I didn't pin down which creation path leaves `triage_at` unset. I read the flow code, and the logs only show the symptom.

**Fix:** in `src/dispatch/case/scheduled.py`, `case_close_reminder` now counts from `case.triage_at or case.created_at`. This replaces the `if case.triage_at:` guard I added earlier, which would have skipped those cases entirely. `created_at` is already loaded by `get_all_by_status`.

**Tests** (added to `tests/case/test_case_scheduled.py`):
- A case in triage with no `triage_at` that is over a week old gets a reminder on a Monday, and no TypeError is logged.
- A case under a week old without `triage_at` gets none.
- When both timestamps exist, `triage_at` wins, so an old `created_at` doesn't trigger a reminder for a recently triaged case.

With the source change reverted, 6 of the 14 tests in that file fail, including the new `created_at` test.

I didn't change `case_stable_reminder`. It still skips cases with no `stable_at`, since you only asked about the close reminder. If you want the same `created_at` fallback there, say so.

----- next turn -----

## Recap

**Symptom:** since mid-August, assignees stopped getting the Monday reminders to close long-running triage and stable cases. The daily triage reminders kept arriving.

**Root cause:** commit `c509d45e` (2025-08-12, "refactor(case): share the weekly reminder check") added `_is_reminder_day()` in `src/dispatch/case/scheduled.py`. It compares `date.today().isoweekday()` with `calendar.MONDAY`. `isoweekday()` counts Monday as 1, but `calendar.MONDAY` is 0, so the check is never true. Both `case_close_reminder` and `case_stable_reminder` call it, so they skipped every case on every day, with nothing in the logs.

**Deploy:** production moved from image `main-b05613b5` to `main-81d8ae42` on 2025-08-13 at about 16:40Z. `81d8ae42` is the first deployed commit that contains `c509d45e`.

**Timeline:**
- Monday 2025-08-11 (old build): case close reminders were sent.
- Monday 2025-08-18 (new build): none were sent. The stable reminder ran with no error and sent nothing. This was the first Monday after the deploy.

**Separate bug:** the evening `TypeError` came from `case_close_reminder` subtracting `case.triage_at`, which is None for cases that never went through the triage transition flow. That is the only place `triage_at` gets set.

**Fixes (uncommitted):**
- The weekday check now uses `weekday()`.
- The close reminder counts from `triage_at`, or from `created_at` when `triage_at` is missing.
- Regression tests are in `tests/case/test_case_scheduled.py`. They fail on the old code and pass now.

I left `case_stable_reminder` unchanged. It still skips cases with no `stable_at`.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e
DEPLOYED_IMAGE: main-81d8ae42
FIRST_MISSED: 2025-08-18
MISSING_FIELD: triage_at