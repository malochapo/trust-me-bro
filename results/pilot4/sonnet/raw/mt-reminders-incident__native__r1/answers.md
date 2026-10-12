**Root cause:** commit `c509d45e` ("refactor(case): share the weekly reminder check", Jordan Lee, 2025-08-12) broke the Monday check in `src/dispatch/case/scheduled.py`.

The refactor replaced the inline condition `date.today().isoweekday() == 1` with a helper, `_is_reminder_day()`. The helper compares `isoweekday()` against `calendar.MONDAY`. Python's `isoweekday()` returns 1 for Monday, but `calendar.MONDAY` is 0, because the `calendar` module counts weekdays from Monday = 0. The comparison is therefore never true, on any day of the week.

Both `case_close_reminder` (long-running triage cases) and `case_stable_reminder` (stable cases) gate on `q >= 1 and _is_reminder_day()`. Neither has sent anything since the change. Nothing raises an error, so no exception is logged. The daily triage reminder (`case_triage_reminder`) doesn't use the helper, which is why it still arrives.

**The deploy:** the scheduler and web pods were redeployed on **2025-08-13 at about 16:40Z**, with image `registry.example.com/dispatch:main-81d8ae42`.
- The previous image, `main-b05613b5`, was deployed on 2025-07-30. It does not contain `c509d45e`.
- `81d8ae42` is a descendant of `c509d45e`, and it was committed on 2025-08-12.
- The same deploy also brought in `bce2fca2`, `32fa810f` and `92f13c0a`, but none of those touch the reminder gating.

**Log evidence:**

| Monday | "Case close reminder sent" lines | Image running |
|---|---|---|
| 07-28 | 4 | `main-b05613b5` |
| 08-04 | 6 | `main-b05613b5` |
| 08-11 | 5 | `main-b05613b5` |
| 08-18 | **0** | `main-81d8ae42` |

On 08-18 at 18:00 both jobs ran and logged no reminders for stable or triage cases, with no reminder-related errors other than the `triage_at` one below. The first Monday after the deploy, 08-18, is the first one missed.

**Other findings, not the cause:**
- `case_close_reminder` and `case_stable_reminder` log `TypeError: datetime - NoneType` almost daily. For `case_stable_reminder` this was already guarded in `32fa810f`, which shipped in the same deploy. `case_close_reminder` still has the problem, because it reads `case.triage_at` unguarded. That is a separate bug that skips the cases with no `triage_at`.
- The database restart on 2025-08-15 around 14:40Z caused a burst of connection errors, but it was not on a Monday and doesn't explain the missing reminders.

**Fix, for when you want it:** use `date.today().weekday() == calendar.MONDAY`, or compare `isoweekday() == 1`. A small unit test that mocks Monday would have caught this. Reminders for cases past the one-week threshold should resume on the next Monday after the fix ships. I haven't changed any code.

----- next turn -----

The Monday check is fixed, and a regression test now covers it.

- **Fix:** in `src/dispatch/case/scheduled.py`, `_is_reminder_day()` now compares `date.today().weekday()` with `calendar.MONDAY`. Both count Monday as 0, which is what the refactor had mismatched.
- **Test:** the new `tests/case/test_case_scheduled.py` patches `date.today()` for a Monday (2025-08-18) and for each of the other six days. It expects true only on the Monday.
- **Verification:** all 7 cases pass with the fix. With the fix stashed, the Monday case fails, so the test would have caught the original bug. I ran only the new test file, not the full suite.

Nothing is committed. The unguarded `case.triage_at` bug in `case_close_reminder` is still there. I left it alone because it is a separate issue. Say if you want that guarded as well.

----- next turn -----

The TypeError comes from cases that have no `triage_at`, and `case_close_reminder` now falls back to `created_at` for them. All 11 tests in `tests/case/test_case_scheduled.py` pass. I ran only that file, not the full suite.

**Cause:** `case_close_reminder` computed `datetime.utcnow() - case.triage_at` with no check for a missing value. `triage_at` is nullable. The only place that sets it is `case_triage_status_flow`, and that runs only on the New→Triage and Closed→Triage transitions. A case that is created directly in triage status, or that reaches triage another way, never gets a timestamp. I didn't confirm from the logs which of those paths produced the affected cases.

The exception was caught per case, so the job kept running. It logged the error every evening and skipped those cases, so they never got their weekly reminder. This was already broken before the Monday-check regression, and it would have kept those cases silent even after that fix.

**Fix:** `case_close_reminder` in `src/dispatch/case/scheduled.py` now counts from `case.triage_at or case.created_at`.

**Tests:** the new tests cover four cases:
- A case with `triage_at` set counts from it.
- A case with no `triage_at` and 8 days old gets the reminder, with no TypeError logged.
- A case with no `triage_at` and 2 days old gets nothing.
- Nothing is sent on a non-Monday.

The scheduler decorator returns `None`, so the tests fetch the job from `scheduler.registered_tasks` and unwrap it. With the source changes stashed, the fallback test and the Monday test both fail.

`case_stable_reminder` still skips cases with no `stable_at`, without logging anything. That was the earlier `32fa810f` fix. You only asked about the close reminder, so I left it, but stable cases with no timestamp may be silently missing reminders too. Say if you want the same fallback there.

Nothing is committed. Both fixes are still uncommitted changes in `scheduled.py`.

----- next turn -----

**Recap**

- **Weekday bug:** commit `c509d45e` (2025-08-12) moved the Monday check into a helper, `_is_reminder_day()`. The helper compared `isoweekday()`, where Monday is 1, against `calendar.MONDAY`, which is 0. The condition was never true. The weekly close reminders for triage and stable cases silently stopped, while the daily triage reminder kept working because it doesn't use the helper.
- **Deploy:** the image `main-81d8ae42` went out on 2025-08-13 at about 16:40Z. The previous image, `main-b05613b5`, did not contain the commit. The last Monday with reminders was 2025-08-11, and 2025-08-18 had none.
- **Evening TypeError:** `case_close_reminder` subtracted `case.triage_at` without checking for `None`. That timestamp is only set on the New→Triage and Closed→Triage transitions, so cases created directly in triage never get one. The exception was caught per case, so those cases were skipped and logged an error every evening.
- **Fixes:** `_is_reminder_day()` now uses `weekday()`, and the close reminder counts from `triage_at or created_at`. `tests/case/test_case_scheduled.py` has 11 tests that pass. The two regression tests fail without the fixes. Nothing is committed.
- **Open item:** `case_stable_reminder` still silently skips cases with no `stable_at`. I did not change it.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e97f4eeacf950450c142ee27da8fcda3f
DEPLOYED_IMAGE: registry.example.com/dispatch:main-81d8ae42
FIRST_MISSED: 2025-08-18
MISSING_FIELD: triage_at