**Root cause:** commit `c509d45e` ("refactor(case): share the weekly reminder check", Jordan Lee, 2025-08-12) broke the Monday check. It replaced `date.today().isoweekday() == 1` with a new helper, `_is_reminder_day()` in `src/dispatch/case/scheduled.py`. The helper compares `isoweekday()` to `calendar.MONDAY`.

- `isoweekday()` numbers Monday as 1.
- `calendar.MONDAY` is 0. I ran `python3 -c "import calendar;print(calendar.MONDAY)"` and it printed 0.
- So `_is_reminder_day()` is never true.
- `case_close_reminder` (long-running triage cases) and `case_stable_reminder` (stable cases) both gate on it, so neither sends anything now. Neither raises an error or writes a log line when it skips.

**Why the daily triage reminders still arrive:** `case_triage_reminder` doesn't use the Monday check.

**Deploy that shipped it:** image `registry.example.com/dispatch:main-81d8ae42`, which is the fix(case) "exclude resolved_by in update" commit (#6183, 2025-08-12). It includes `c509d45e` (confirmed with `git merge-base --is-ancestor`). The logs show it rolling out on 2025-08-13 at 16:40Z.

- **Scheduler:** pod `scheduler-mhtsgqwwx-q5q2n` started that image at 16:40:06Z.
- **API:** pod `web-5dkmr9s9s-xxktx` started it at 16:40:07Z.

**Evidence from the logs:** "Case close reminder sent to …" lines appear only on Mondays before the deploy.

| Monday | Reminders sent |
|---|---|
| 07-28 | 4 |
| 08-04 | 6 |
| 08-11 | 5 |
| 08-18 | 0 (first Monday after the deploy) |

The previous image was `main-b05613b5`, deployed 2025-07-30 and running through the 08-11 Monday, so it still sent reminders. `b05613b5` does not contain `c509d45e`. The only Monday in the log window after the deploy is 08-18, so that is the one data point on the new build. It is consistent with the bug but is a single Monday.

**Not the cause:**

- **`datetime - None` TypeError:** it is logged at 18:00 every day from 07-28, before the regression. It comes from `case.triage_at` and `case.stable_at` being `None` on some cases, in an older version of the code.
- **DB outage:** the connection-refused errors on 08-15 are a separate incident.

**Fix, when you want it:** use `isoweekday() == 1`, or `date.today().weekday() == calendar.MONDAY`. A small test for the helper would stop this recurring. Cases that missed the 08-18 reminder will only be picked up on the next Monday after the fix is deployed. I haven't changed any code.

----- next turn -----

I saved the findings to memory, so a new session can pick this up:

- the root cause (`calendar.MONDAY` is 0 but `isoweekday()` counts Monday as 1)
- the commit that introduced it (`c509d45e`)
- the deploy that shipped it (image `main-81d8ae42`, rolled out 2025-08-13)
- the log evidence
- the red herrings
- the proposed fix, which is not applied yet

----- next turn -----

Fixed `_is_reminder_day()` in `src/dispatch/case/scheduled.py` and added a regression test. I haven't committed either change.

**Cause:** commit `c509d45e` added `_is_reminder_day()` as `date.today().isoweekday() == calendar.MONDAY`. `isoweekday()` returns 1 for Monday but `calendar.MONDAY` is 0, so the check never passed. `case_close_reminder` (triage) and `case_stable_reminder` both depend on it, so both stopped sending.

**Fix:** it now uses `date.today().weekday() == calendar.MONDAY`.

**Test:** `tests/case/test_case_scheduled.py` mocks today's date and checks a Monday, a Tuesday and a Sunday. It passes with the fix. With the fix stashed, the Monday case fails, so it would have caught the bug.

**Evidence in the logs:**
- "Case close reminder sent" appears on 2025-07-28, 08-04 and 08-11, and not on 08-18.
- Commit `c509d45e` is an ancestor of `81d8ae42`, the commit the `main-81d8ae42` image is built from.
- That image rolled out on 2025-08-13 at about 16:40Z, so 08-18 was the first Monday after it.
- I only ran the new test file, not the full suite.

Cases that were missed only get reminded on the first Monday after this fix is deployed.

`case_close_reminder` also logs a `datetime - None` error for cases with no `triage_at`. That predates the regression and I left it alone.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e
DEPLOYED_IMAGE: main-81d8ae42
FIRST_MISSED: 2025-08-18