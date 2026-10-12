**Root cause:** commit `c509d45e` ("refactor(case): share the weekly reminder check", Jordan Lee, 2025-08-12) broke the Monday check. It replaced `date.today().isoweekday() == 1` with a new helper, `_is_reminder_day()`, in `src/dispatch/case/scheduled.py`. The helper compares `isoweekday()` to `calendar.MONDAY`. `isoweekday()` returns 1 for Monday, but `calendar.MONDAY` is 0 (I checked in Python). So the helper is never true on a Monday. It is true on no day at all, because `isoweekday()` never returns 0. Both `case_close_reminder` (long-running triage cases) and `case_stable_reminder` (stable cases) gate on `q >= 1 and _is_reminder_day()`. Neither has sent anything since the change shipped. The daily triage reminder doesn't use the helper, which is why it kept working.

**Deploy that shipped it:** image `registry.example.com/dispatch:main-81d8ae42`, rolled out on 2025-08-13 at about 16:40 UTC.
- Both the scheduler pod (`scheduler-mhtsgqwwx-q5q2n`) and the API pod (`web-5dkmr9s9s-xxktx`) started that image at that time, replacing `main-b05613b5`, which had been running since 2025-07-30.
- `git merge-base --is-ancestor` shows `c509d45e` is in `81d8ae42` and not in `b05613b5`.
- The new pod's tracebacks show line numbers shifted by 4 in `case_close_reminder` (line 47 where it was 43). That matches the helper's added lines.

**Timeline from the logs**

| Monday | "Case close reminder sent" lines |
|---|---|
| 07-28 | 4, from the old image |
| 08-04 | 6, from the old image |
| 08-11 | 5, from the old image, before the rollout |
| 08-18 | none, first Monday on the new image |

The 08-18 run still logs the daily triage reminder and the `case_close_reminder` error, but no close reminders. So the regression is visible from 08-18, the first Monday after the 08-13 rollout. The Monday 08-11 reminders were still sent.

**Not the cause:**
- The `unsupported operand type(s) for -: 'datetime' and 'NoneType'` errors appear daily from 07-28. They come from a case with `triage_at` unset in `case_close_reminder`, and they predate the break.
- `32fa810f` (the `stable_at` None guard) shipped in the same image. It explains why the stable reminder's error disappeared on 08-13, and it is unrelated to the missing reminders.

**Fix (not applied, as requested):** `isoweekday() == calendar.MONDAY + 1`, or better `date.today().weekday() == calendar.MONDAY`. A regression test that freezes a Monday date would have caught this. Since 08-18 no Monday reminders have gone out, and 08-25 and later were presumably missed too. The logs end 08-20, so I couldn't check those.

----- next turn -----

I fixed the Monday check and added a regression test. The new test passes with the fix. Against the old code, the two Monday cases fail, so the test would have caught the bug. I haven't run the rest of the suite or committed anything.

- **Fix:** in `src/dispatch/case/scheduled.py`, `_is_reminder_day()` now compares `date.today().weekday()` to `calendar.MONDAY`. Both use the same 0-based numbering, where the old `isoweekday()` was 1-based. The close and stable reminders both use this helper, so one change covers both.
- **Test:** `tests/case/test_case_scheduled.py` checks `_is_reminder_day()` on real dates in August 2025. It expects true on Mondays 08-18 and 08-25 and false on Tuesday 08-19, Wednesday 08-20 and Sunday 08-24. It patches the module's `date` object because `freezegun` isn't installed.
- **Not covered:** the test checks the helper, not `case_stable_reminder` or `case_close_reminder` themselves. The scheduler decorator doesn't return the function and the job needs a database session, so a job-level test would be heavier. Say if you want one.

The fix still has to be deployed before Monday reminders resume.

----- next turn -----

The nightly TypeError is fixed. Cases with no `triage_at` now count their age from `created_at`, so they still get the weekly reminder. All tests under `tests/case` pass. Nothing is committed.

**Cause:** `case_close_reminder` computed `datetime.utcnow() - case.triage_at`. `triage_at` is only set by `case_triage_status_flow` (in `case/flows.py`), which runs on the New → Triage and Closed → Triage transitions. A case created directly in Triage status never goes through that flow, so its `triage_at` stays NULL. That subtraction then raises the `TypeError`. The per-case `try/except` logs it and skips the case, so those cases never got a reminder. That is also why the error appears every evening, not just on Mondays. I inferred "created directly in Triage" from the code and did not confirm it against data.

**Fix:** In `src/dispatch/case/scheduled.py`, the job now uses `case.triage_at or case.created_at` as its start point.

**Test:** The new test in `tests/case/test_case_scheduled.py` runs the job on a Monday and covers four cases:
- `triage_at` missing, created 10 days ago: sends.
- `triage_at` missing, created 2 days ago: doesn't send.
- `triage_at` set to 10 days ago, created 20 days ago: sends.
- `triage_at` set to 2 days ago, created 20 days ago: doesn't send.

Without the fix, the first case fails with the same TypeError.

**Stable reminder:** `case_stable_reminder` still skips cases with no `stable_at`, which was the earlier `32fa810f` fix. You only asked about the close reminder, so I left it. Say if you want it to count from `created_at` too.

----- next turn -----

**Recap**

- **Symptom:** From mid-August, assignees stopped getting the Monday reminders to close long-running triage and stable cases. The daily triage reminder kept working.
- **Root cause:** Commit `c509d45e` (2025-08-12, "refactor(case): share the weekly reminder check") added `_is_reminder_day()`. It compares `date.today().isoweekday()` to `calendar.MONDAY`. `isoweekday()` returns 1 for Monday, but `calendar.MONDAY` is 0, so the check was never true. Both `case_close_reminder` and `case_stable_reminder` use it, so neither sent anything. The daily triage reminder doesn't use it.
- **Deploy:** Image `registry.example.com/dispatch:main-81d8ae42` replaced `main-b05613b5` on the scheduler and API pods at about 2025-08-13 16:40 UTC. `c509d45e` is in `81d8ae42` and not in `b05613b5`.
- **Evidence:**
  - Close reminders were sent on Mondays 07-28, 08-04 and 08-11.
  - None were sent on 08-18, the first Monday after the rollout.
  - The logs end 08-20, so later Mondays aren't checked.
- **Fix:** `_is_reminder_day()` now uses `weekday() == calendar.MONDAY`. The regression test checks it on real Mondays and non-Mondays.
- **Second issue (unrelated, older):** `case_close_reminder` logged a `TypeError` every evening because cases created directly in Triage never get `triage_at`. The subtraction then fails and the case is skipped. The job now counts from `created_at` when `triage_at` is missing, and there is a test for it. `case_stable_reminder` still skips cases with no `stable_at`.
- **State:** Both fixes and the tests are in the working tree, uncommitted. `tests/case` passes (24 tests). The fix is not deployed yet.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e
DEPLOYED_IMAGE: registry.example.com/dispatch:main-81d8ae42
FIRST_MISSED: 2025-08-18
MISSING_FIELD: triage_at