**Root cause:** commit `c509d45e` ("refactor(case): share the weekly reminder check", Jordan Lee, 2025-08-12) broke the Monday check. It was shipped to production on 2025-08-13 at ~16:40 UTC as image `main-81d8ae42`.

The refactor added a helper in `src/dispatch/case/scheduled.py:31`:

```python
def _is_reminder_day() -> bool:
    return date.today().isoweekday() == calendar.MONDAY
```

The two are on different numbering schemes. `isoweekday()` is 1–7, so Monday is 1 and Sunday is 7. `calendar.MONDAY` is 0, because the `calendar` module counts weekdays from 0. So the helper is true only when `isoweekday()` returns 0, which never happens, and it is always false. Both `case_close_reminder` (triage cases) and `case_stable_reminder` call it in place of the old `date.today().isoweekday() == 1`. As a result, the weekly reminders are never sent. `case_triage_reminder` doesn't use the helper, which is why the daily triage reminders kept arriving. No settings were involved.

**Evidence from the logs:**
- **Image change:** the kubelet lines show the scheduler and web pods ran `main-b05613b5` from 2025-07-30 17:10 UTC. Both were replaced with `main-81d8ae42` on 2025-08-13 16:40 UTC. Those are the only two deploys in the window.
- **Sends before the deploy:** "Case close reminder sent" appears 15 times, all on Mondays, on 07-28, 08-04 and 08-11. There are none on Monday 08-18 or after the deploy.
- **Code moved:** the scheduler traceback for `case_close_reminder` was at `scheduled.py` line 43 on the old image and is at line 47 on the new one. That shift matches the refactor adding the helper.
- **In the deployed image:** `81d8ae42` is the tip of the deployed image. `c509d45e` is an ancestor of it, alongside `32fa810f` ("not all cases have a stable_at date"). The deploy also picked up `7c446bd6` and `81d8ae42`, which don't touch this code.

**Not the cause:** every day the scheduler logs `unsupported operand type(s) for -: 'datetime.datetime' and 'NoneType'` from `case_close_reminder` and `case_stable_reminder`. It appears on both the old and the new image, and the reminders still worked on 08-04 and 08-11, so it didn't cause this outage. It's worth a separate look. Cases with no `triage_at` or `stable_at` raise there, and the surrounding try/except logs that and moves on to the next case, which may mean some cases are skipped.

**Fix, when you want it:** compare against `calendar.MONDAY + 1`, or use `date.today().weekday() == calendar.MONDAY`. `weekday()` is 0-based like `calendar`. I'd also add a test that mocks a Monday and a Tuesday. I haven't changed any code.

----- next turn -----

The weekly reminders should work again once this ships. I changed `_is_reminder_day()` in `src/dispatch/case/scheduled.py` to use `date.today().weekday() == calendar.MONDAY`. `weekday()` counts Monday as 0, the same as `calendar.MONDAY`. I haven't committed anything.

I added `tests/case/test_case_scheduled.py`. It runs `_is_reminder_day()` against each day of the week of 2025-08-18, with `date` patched in the module, and expects true only on Monday. It passes with the fix. With the fix stashed, the Monday case fails, so it would have caught the original bug.

I only ran the new test file, not the full suite.

The fix needs a deploy, and then the next Monday 18:00 run will send the close reminders again. The `NoneType` error from cases with no `triage_at` or `stable_at` is still there, as I mentioned earlier.

----- next turn -----

The nightly TypeError is fixed, and cases with no `triage_at` now get their weekly reminder, counted from creation. I haven't committed anything.

**Cause:** `case_close_reminder` computed `datetime.utcnow() - case.triage_at` for every case in triage status. `triage_at` is only set when a case goes through a status transition (`case_triage_status_flow` in `src/dispatch/case/flows.py`). Cases that start in triage, or were already there before that code existed, have `triage_at = NULL`. Subtracting `None` raised the TypeError. The surrounding try/except logged it and moved on, so it was logged every evening and those cases never got a reminder.

**Fix:** in `src/dispatch/case/scheduled.py` the job now uses `case.triage_at or case.created_at` as the starting point.

**Tests:** I added three tests to `tests/case/test_case_scheduled.py`.
- A case with no `triage_at` and a 10-day-old `created_at` gets a reminder and logs no exception.
- A case with no `triage_at` created 2 days ago does not get a reminder.
- A case with a recent `triage_at` and an old `created_at` does not get a reminder, so `triage_at` still takes precedence.

The `tests/case` directory passes (25 tests). With the source fix stashed, the two no-`triage_at` tests fail (the precedence test passes either way).

I left `case_stable_reminder` alone. It silently skips cases with no `stable_at` (the TypeError there was already fixed in `32fa810f`). You only asked about the close reminder, so say if you want it to count from creation too.

----- next turn -----

**Recap**

- **Symptom:** from mid-August, assignees stopped getting the weekly Monday reminders for long-running triage and stable cases. The daily triage reminders kept working.
- **Root cause:** commit `c509d45e` ("refactor(case): share the weekly reminder check", 2025-08-12) added a helper, `_is_reminder_day()`, that compared `date.today().isoweekday()` with `calendar.MONDAY`. `isoweekday()` returns 1 for Monday, but `calendar.MONDAY` is 0, so the helper was always false. The close and stable reminder jobs both use it, so neither could send. The daily triage reminder doesn't use it.
- **Deploy:** the logs show only two deploys in the window. Image `main-b05613b5` ran from 2025-07-30 and was replaced by `main-81d8ae42` on 2025-08-13 at ~16:40 UTC. The new image contains the refactor.
- **Timeline:** reminders were sent on Mondays 07-28, 08-04 and 08-11. Monday 08-18 was the first Monday after the deploy, and nothing was sent.
- **Fix:** `_is_reminder_day()` now uses `date.today().weekday() == calendar.MONDAY`. A parametrized test over a full week fails on the old code and passes on the new.
- **Separate nightly TypeError:** `case_close_reminder` subtracted `case.triage_at` from the current time. Cases that never went through a status transition have no `triage_at`, so the subtraction raised and the case was skipped. It predates the outage and wasn't connected to it. The job now counts from `created_at` when `triage_at` is missing, and three tests cover that. `tests/case` passes (25 tests).
- **Still open:** neither fix is committed, and neither is deployed, so reminders won't resume until a build with both goes out. `case_stable_reminder` still skips cases with no `stable_at` without sending anything.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e
DEPLOYED_IMAGE: main-81d8ae42
FIRST_MISSED: 2025-08-18
MISSING_FIELD: triage_at