## Root cause

The refactor in `c509d45e` broke the Monday check. `_is_reminder_day()` in `src/dispatch/case/scheduled.py:31-33` compares against the wrong constant:

```python
def _is_reminder_day() -> bool:
    return date.today().isoweekday() == calendar.MONDAY
```

- `calendar.MONDAY` is `0`, because Python's `calendar` numbers Monday as 0.
- `date.isoweekday()` numbers Monday as 1.

So `isoweekday() == calendar.MONDAY` is never true, on any day. The original inline check in that commit's diff was `date.today().isoweekday() == 1`, which was correct. The refactor replaced the `1` with `calendar.MONDAY` and changed the meaning.

`_is_reminder_day()` gates both long-running reminders: `case_close_reminder` (triage cases, `scheduled.py:49`) and `case_stable_reminder` (stable cases, `scheduled.py:95`). Both now silently send nothing. The daily triage reminder (`case_triage_reminder`) doesn't call the helper, which is why it still arrives.

## Evidence from the logs

- **Last successful close reminders:** Monday 2025-08-11 at 18:00 UTC. The scheduler sent 5 "Case close reminder sent" lines that day, from the image built before the refactor.
- **First missed run:** Monday 2025-08-18. The only reminder lines that day are "Case triage reminder sent" and "Incident close reminder sent", as expected. No case close or stable reminders.
- **Nothing else changed the settings:** the reminder jobs run daily at 18:00, and the errors above are the only failures in those jobs.

## The deploy that shipped it

- Commit: `c509d45e` "refactor(case): share the weekly reminder check", Aug 12 2025, by Jordan Lee.
- The scheduler pod started on image `registry.example.com/dispatch:main-81d8ae42` at **2025-08-13T16:40:06Z**. That image is `81d8ae42` "fix(case): exclude resolved_by in update (#6183)", and `c509d45e` is an ancestor of it (checked with `git merge-base --is-ancestor`).
- The web pods were also moved to `main-81d8ae42` at 16:40:07Z.

## Related but not the cause

The `case_stable_reminder` log shows an error every day from 2025-07-28 to 2025-08-12: `unsupported operand type(s) for -: 'datetime.datetime' and 'NoneType'` on `case.stable_at`. That is a separate bug, fixed in `32fa810f` (Aug 11). It was already in the 07-30 image, but it only errored on individual cases and the Monday sends still worked on 08-04 and 08-11, so it does not explain the drop. Note that `case_close_reminder` and `case_stable_reminder` both use the same helper, so the same one-line fix covers both.

I haven't changed any code. The likely fix is `date.today().weekday() == calendar.MONDAY` (or `isoweekday() == 1`), with a test that runs on a fixed Monday date. Tell me if you want me to make that change.

----- next turn -----

I fixed the weekday check and added regression tests. They fail on the broken code and pass on the fix.

**The fix** (`src/dispatch/case/scheduled.py:33`): `_is_reminder_day()` now uses `date.today().weekday() == calendar.MONDAY`. Both sides use Python's Monday-is-0 convention. The previous `isoweekday()` compared a Monday-is-1 value to `calendar.MONDAY` (0), so it was never true.

**The tests** (new file `tests/case/test_case_scheduled.py`):
- `test_is_reminder_day`: freezes `date.today()` on each day from Monday 2025-08-11 through Sunday 2025-08-17, and asserts only Monday returns True.
- `test_case_stable_reminder_sends_on_monday`: runs the real stable reminder job on a Monday with a case stable for 14 days, and asserts the reminder is sent. This is the end-to-end path that broke in production.
- `test_case_stable_reminder_skips_other_days`: same setup on a Tuesday, asserts nothing is sent.

The job functions are registered with the scheduler, so the tests look up the registered task by name and unwrap its decorators to call the raw function with the test session.

**Verification:**
- `python -m pytest tests/case/test_case_scheduled.py`: 9 passed.
- With the old `isoweekday()` line temporarily restored, 2 tests failed: the Monday case of `test_is_reminder_day` and `test_case_stable_reminder_sends_on_monday`. I then restored the fix.
- `python -m pytest tests/case`: 24 passed.

I didn't run the full suite. The changes are in `scheduled.py` and the new test file only, and nothing else was modified. Nothing is committed.

----- next turn -----

The close reminder job was raising a TypeError for triage cases that have no `triage_at`. It now counts those cases from `created_at`, and they get their weekly reminder. The fix is in and tested.

**Cause:** `case_close_reminder` (`src/dispatch/case/scheduled.py:50`) computes `datetime.utcnow() - case.triage_at`. When `triage_at` is `None`, Python raises `TypeError: unsupported operand type(s) for -: 'datetime.datetime' and 'NoneType'`. The job catches it per case and logs it, which is why it shows up every evening. `triage_at` is only set when a case transitions to Triage through the flow (`src/dispatch/case/flows.py:594-596`), so cases that reached Triage another way never get it. The error happens before the Monday check, so it appears on every day of the week.

**Fix:** `triage_started = case.triage_at or case.created_at`, and the span is measured from `triage_started`. The existing `try/except` and the Monday gate are unchanged.

**Tests** (added to `tests/case/test_case_scheduled.py`):
- `test_case_close_reminder_counts_from_created_at_when_triage_at_missing`: a Triage case with no `triage_at` and `created_at` 14 days ago gets a reminder on a Monday. Without the fix this test fails.
- `test_case_close_reminder_does_not_raise_when_triage_at_missing`: a case created 2 days ago with no `triage_at` on a Tuesday is not reminded, and the job completes without error.

`python -m pytest tests/case`: 26 passed. I also confirmed the first new test fails when the fallback is removed.

Nothing is committed. Two things I left alone:
- `case_stable_reminder` still skips stable cases with no `stable_at` entirely, instead of falling back to a creation date. You only asked for the close job, so I didn't change it; say if you want the same fallback there.
- The 2025-07-28 logs for the stable job show the same error type from before the `stable_at` fix (`32fa810f`), which is already deployed to main, not yet to production.

----- next turn -----

Here is the recap for the incident report. Everything in it comes from the logs and the repo history I checked earlier.

## Recap

**Summary:** Since the 2025-08-13 deploy, the weekly Monday reminders for long-running triage and stable cases have not been sent. Daily triage reminders kept working. The bug is in a helper that was refactored on 2025-08-12.

**Root cause:** `_is_reminder_day()` compared `date.today().isoweekday()` (Monday = 1) against `calendar.MONDAY` (Monday = 0). The comparison was never true, so `case_close_reminder` and `case_stable_reminder` never sent their weekly reminders. The refactor was `c509d45e` ("refactor(case): share the weekly reminder check", 2025-08-12). The original inline check was `isoweekday() == 1`, which was correct.

**Timeline:**
- 2025-08-11 (Monday): last successful weekly reminders, sent by the image built before the refactor.
- 2025-08-13 16:40 UTC: scheduler restarted on `main-81d8ae42`, which includes `c509d45e`.
- 2025-08-18 (Monday): first missed run. Only triage and incident-close reminders were sent that day.

**Fix:** `date.today().weekday() == calendar.MONDAY`. Regression tests cover every weekday and the end-to-end stable job on a Monday and a Tuesday. Without the fix, the Monday tests fail.

**Separate evening TypeError:** `case_close_reminder` subtracted `case.triage_at` from `utcnow()`. Cases that reached Triage without going through the flow (`src/dispatch/case/flows.py:594-596` is the only place `triage_at` is set) have it as `None`. The error was caught per case, so it was logged each evening and only those cases were skipped. The job now falls back to `case.created_at`. Two tests cover it: one checks that the reminder is sent, and one checks that a too-new case doesn't raise or get reminded.

**Status:** The fixes to `scheduled.py` and the new test file are uncommitted and not deployed. Also not changed: `case_stable_reminder` still skips stable cases with no `stable_at`, which I didn't change because you only asked about the close job.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e
DEPLOYED_IMAGE: main-81d8ae42
FIRST_MISSED: 2025-08-18
MISSING_FIELD: triage_at