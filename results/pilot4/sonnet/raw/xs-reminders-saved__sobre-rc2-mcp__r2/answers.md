The Monday reminders stopped because of a refactor that swapped the Monday check for one that can never be true. It reached production in the image deployed on 2025-08-13 at 16:40Z. I haven't changed any code.

**Root cause**
- Commit `c509d45e` ("refactor(case): share the weekly reminder check", Jordan Lee, 2025-08-12) replaced `date.today().isoweekday() == 1` with a shared helper, `_is_reminder_day()` in `src/dispatch/case/scheduled.py`.
- The helper returns `date.today().isoweekday() == calendar.MONDAY`.
- `isoweekday()` runs from 1 (Monday) to 7 (Sunday), but `calendar.MONDAY` is 0, because the `calendar` module counts weekdays from 0.
- So the condition is never true on any day, and the refactor silently turned off Monday sending in both `case_close_reminder` (long-running triage cases) and `case_stable_reminder` (stable cases).
- The daily triage reminder doesn't use this check, which is why it kept arriving.

**Evidence from the logs**
- "Case close reminder sent" lines appear on Mondays 07-28, 08-04 and 08-11 (5, 7 and 6 sends).
- There are none on Monday 08-18 or on any other day after that. The 08-18 close-reminder line is an incident reminder, not a case one.
- The scheduler still ran both jobs at 18:00 every day, so nothing failed loudly. They just never sent.

**The deploy**
- The deploy is the scheduler container (and the web container) switching from `registry.example.com/dispatch:main-b05613b5` to `main-81d8ae42` at 2025-08-13T16:40Z.
- The previous image `main-b05613b5` had been running since 2025-07-30T17:10Z.
- `81d8ae42` is "fix(case): exclude resolved_by in update (#6183)", from 2025-08-12. It is not the culprit by itself, but it is the first deployed commit that contains `c509d45e`.
- `b05613b5` is an ancestor-free baseline for this: it contains neither the refactor nor the earlier stable_at fix.

**A related error you'll see in the logs**
- Every day from 07-28 to 08-20, `case_close_reminder` and `case_stable_reminder` log "unsupported operand type(s) for -: 'datetime' and 'NoneType'", from cases with no `triage_at` or `stable_at`.
- `32fa810f` (#6179, 2025-08-11) guards the `stable_at` case, but it was only deployed on 08-13.
- That error was already in the logs while Monday reminders were still going out, so it isn't the cause. After the refactor, `case_close_reminder` still logs the `triage_at` error daily, with no guard on that field.

**Fix, for when you want it**
Either restore `== 1` or compare against `calendar.MONDAY + 1`. A one-line test that the helper is true on a Monday would have caught this. I'd also guard `triage_at` the way `stable_at` is guarded.

----- next turn -----

I saved the findings to memory, with a pointer in `MEMORY.md`, so a new session can pick this up. The note covers the root cause, the deploy, the log evidence, the unguarded `triage_at` error and the proposed fix. No code has been changed.

----- next turn -----

Fixed. The weekly Monday close and stable reminders were never sent because `_is_reminder_day()` compared `isoweekday()`, which runs 1–7, to `calendar.MONDAY`, which is 0. It could never be true.

- **Fix:** `_is_reminder_day()` in `src/dispatch/case/scheduled.py` now compares `weekday()` (0-based) to `calendar.MONDAY`. It also takes an optional date so it can be tested.
- **Regression test:** `tests/case/test_case_scheduled.py` checks the helper is true only on a Monday, and that it defaults to today. All 8 tests pass with the fix and all 8 fail without it. I did not run the rest of the suite.
- **Not changed:** the `triage_at` None guard in `case_close_reminder`, which causes the daily NoneType errors but not this bug. I left it out because you didn't ask for it.

The commit `c509d45e` reached production in image `main-81d8ae42`, deployed 2025-08-13 16:40Z. The scheduler logs show the last close reminders on Monday 2025-08-11, so 2025-08-18 was the first Monday missed.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e97f4eeacf950450c142ee27da8fcda3f
DEPLOYED_IMAGE: main-81d8ae42
FIRST_MISSED: 2025-08-18