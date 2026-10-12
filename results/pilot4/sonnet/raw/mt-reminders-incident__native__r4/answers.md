**Root cause:** commit `c509d45e` (Jordan Lee, 2025-08-12, "refactor(case): share the weekly reminder check") broke the Monday check in `src/dispatch/case/scheduled.py`.

The refactor replaced the inline `date.today().isoweekday() == 1` with a helper:

```python
def _is_reminder_day() -> bool:
    return date.today().isoweekday() == calendar.MONDAY
```

`calendar.MONDAY` is `0`, because the `calendar` module numbers weekdays from Monday = 0. `isoweekday()` numbers them from Monday = 1. The comparison is never true, so `_is_reminder_day()` always returns `False`.

Both weekly reminders use it: `case_close_reminder` (long-running triage cases) and `case_stable_reminder` (stable cases). Neither sends anything any more. `case_triage_reminder` doesn't use the helper, which is why the daily triage reminders still arrive. No exception is raised, so nothing shows up in the logs as an error.

**Deploy:** image `registry.example.com/dispatch:main-81d8ae42`, rolled out to production on 2025-08-13 at about 16:40 UTC.
- The scheduler pod `scheduler-xdp7k6gs2q-w6cj7` was replaced by `scheduler-mhtsgqwwx-q5q2n`, and the web pod was replaced at the same time.
- The previous image was `main-b05613b5`, deployed 2025-07-30. It predates the refactor.
- `81d8ae42` is the first image that contains `c509d45e` (I confirmed it is an ancestor of `81d8ae42`). It also contains `32fa810f`, the stable_at None fix.

**Evidence from the logs (scheduler.log):**

| Monday | Case close reminders sent | Image running |
|---|---|---|
| 2025-07-28 | 4 | `main-b05613b5` |
| 2025-08-04 | 7 | `main-b05613b5` |
| 2025-08-11 | 6 | `main-b05613b5` |
| 2025-08-18 | 0 | `main-81d8ae42` |

- 2025-08-11 was the last Monday before the new image started; 2025-08-18 was the first Monday after it.
- On 08-18 the 18:00 run logged only the triage reminder and an incident close reminder. The scheduler job itself ran normally.
- The 08-11 count of 6 is from the old image. Its one visible error was in `case_close_reminder`, in the same per-case try/except that has no effect on the other cases.

**Secondary issue, not the cause:** `case_close_reminder` still does `datetime.utcnow() - case.triage_at` with no None check. `triage_at` is nullable, and the 08-18 log shows it raising `TypeError` for such a case. That error is caught per case and logged. Since `32fa810f` added the `if case.stable_at` guard to `case_stable_reminder`, that job no longer produces these errors.

**Fix:** compare against `calendar.MONDAY` using `date.today().weekday()` instead of `isoweekday()`, or restore `== 1`. A small unit test for `_is_reminder_day()` on a known Monday would have caught this. I haven't changed any code, as you asked.

----- next turn -----

The Monday check is fixed, and a new regression test fails on the old code and passes on the fix. Nothing is committed.

**Fix:** in `src/dispatch/case/scheduled.py`, `_is_reminder_day()` now uses `date.today().weekday() == calendar.MONDAY`. Both sides count Monday as 0, so the comparison can be true again.

**Test:** the new file is `tests/case/test_case_scheduled.py`, with two parts.
- **Helper test:** `_is_reminder_day()` is checked on frozen dates. 2025-08-11 and 2025-08-18 are Mondays and must return true. Tuesday, Friday and Sunday must return false.
- **Job tests:** `case-stable-reminder` and `case-close-reminder` are run directly with a 10-day-old case. They must send a reminder on a Monday (2025-08-18) and not on a Tuesday (2025-08-19). Those jobs are looked up in `scheduler.registered_tasks`, because the `@scheduler.add` decorator returns `None` and leaves nothing to import.

**Results:** with the source fix stashed, 4 of the 9 new tests fail. With the fix, all 9 pass, and the whole `tests/case` directory passes (24 tests).

I did not change the unguarded `case.triage_at` subtraction in `case_close_reminder`. It isn't what stopped the reminders, and it is caught and logged per case. I can add an `if case.triage_at` guard like the one `case_stable_reminder` has if you want it.

Once this is merged and deployed, the first Monday reminders will go out at 18:00 on the next Monday. The 18:00 scheduler log should show "Case close reminder sent" lines for that day.

----- next turn -----

The close reminder no longer raises on cases with a missing `triage_at`; it counts from `created_at` instead. I haven't committed anything, and this edit sits on top of the Monday-check fix from before.

**Cause:** `case_close_reminder` computes `datetime.utcnow() - case.triage_at` for every case in triage status. The only code that sets `triage_at` is `case_triage_status_flow` in `src/dispatch/case/flows.py`, and only when a case goes through a transition to triage. A case that is in triage status but never went through that flow has `triage_at` set to NULL (the column is nullable). Subtracting `None` raises the `TypeError`.

The logs don't show which cases these are, so I can't say why they skipped the flow. Cases from before the column was added in 2022 are one possibility; I didn't check production data.

The error has been logged once each evening since 2025-08-13 (8 lines in the scheduler log). It shows up as a caught per-case error, so it doesn't stop the other cases. Before the Monday fix it was hidden by the always-false Monday check.

**Fix:** in `src/dispatch/case/scheduled.py` the job now uses `case.triage_at or case.created_at` for the age, with a comment saying why. These cases get their weekly reminder once they are more than a week old, measured from creation.

**Test:** `test_case_close_reminder_falls_back_to_created_at` in `tests/case/test_case_scheduled.py` runs on a Monday with a case whose `triage_at` is None.
- A case created 10 days ago must be sent a reminder.
- A case created 3 days ago must not be sent one.
- No exception may be logged in either case.

**Results:** with the source change stashed, 6 tests in that file fail. That includes the 2 new ones. The other 4 are the Monday-check tests from before, which fail without the earlier Monday fix. With the changes in place, all of `tests/case` passes (26 tests).

----- next turn -----

## Recap

**Symptom:** Since mid-August, assignees stopped getting the Monday reminders to close long-running triage and stable cases. The daily triage reminders kept arriving.

**Root cause:** Commit `c509d45e` (2025-08-12, "refactor(case): share the weekly reminder check") replaced an inline `date.today().isoweekday() == 1` with a shared helper, `_is_reminder_day()`. The helper compared `isoweekday()` to `calendar.MONDAY`. Those use different numbering: `isoweekday()` gives Monday as 1, and `calendar.MONDAY` is 0. The comparison was never true, so `case_close_reminder` and `case_stable_reminder` silently sent nothing. `case_triage_reminder` doesn't use the helper, which is why the daily reminders were unaffected. No error was logged.

**Deploy:** Image `registry.example.com/dispatch:main-81d8ae42` replaced `main-b05613b5` on 2025-08-13 at about 16:40 UTC. It is the first image containing `c509d45e`.

**Timeline:**
- Monday 2025-08-11 was the last Monday on the old image. 6 case close reminders went out.
- Monday 2025-08-18 was the first Monday on the new image. 0 went out.
- Monday 2025-08-04 had 7 and 2025-07-28 had 4, both on the old image.

**Secondary bug (the evening `TypeError`):** `case_close_reminder` subtracted `case.triage_at` without a None check. `triage_at` is only set when a case goes through the triage transition flow, so cases in triage status that never went through it have it NULL. The error was logged once each evening from 2025-08-13 on, and it was caught per case, so other cases weren't affected. Before the Monday fix it was masked by the always-false Monday check.

**Changes (uncommitted):**
- **Monday fix:** `src/dispatch/case/scheduled.py` now uses `date.today().weekday() == calendar.MONDAY`.
- **Fallback fix:** the same file now counts the age from `case.triage_at or case.created_at`.
- **Tests:** `tests/case/test_case_scheduled.py` is new. It checks the helper on frozen dates and runs both weekly jobs on a Monday and a Tuesday. It also covers the `created_at` fallback. With the source fixes stashed, 6 of its 11 tests fail. With the fixes, all of `tests/case` passes (26 tests).

**Not done:** nothing is committed or deployed, so reminders resume only after a deploy. The next confirmation is the first Monday 18:00 run afterwards. I also didn't find out why those cases have a NULL `triage_at`, because the logs don't identify them.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e
DEPLOYED_IMAGE: registry.example.com/dispatch:main-81d8ae42
FIRST_MISSED: 2025-08-18
MISSING_FIELD: triage_at