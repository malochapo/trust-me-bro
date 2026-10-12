Root cause and deploy are both identified, and I didn't change any code.

**Root cause**

Commit `c509d45e` ("refactor(case): share the weekly reminder check", Jordan Lee, 2025-08-12) changed the Monday check in `src/dispatch/case/scheduled.py`. The old check was `date.today().isoweekday() == 1`. The new helper `_is_reminder_day()` uses `date.today().isoweekday() == calendar.MONDAY`.

The two are not equivalent. `isoweekday()` numbers Monday as 1, but `calendar.MONDAY` is 0 (I confirmed this by running it). So the check is never true on any day, and `case_close_reminder` (triage cases) and `case_stable_reminder` (stable cases) silently stop sending anything. Nothing is logged and nothing errors.

The daily triage reminder (`case_triage_reminder`) doesn't use the helper, so it kept working. That matches what you're seeing.

**Evidence in the logs**

- "Case close reminder sent" lines appear on Monday 07-28 (5), 08-04 (7) and 08-11 (6). There are none on Monday 08-18.
- On 08-18 the scheduler did send an incident close reminder. The scheduler itself was running, and only the case reminders were missing.

**The deploy that shipped it**

- The scheduler and web pods were restarted together on 2025-08-13 at about 16:40Z. Both moved from image `main-b05613b5` (running since 07-30 17:10Z) to `main-81d8ae42`.
- `81d8ae42` is "fix(case): exclude resolved_by in update (#6183)", dated 2025-08-12.
- `c509d45e` is an ancestor of `81d8ae42` and is not in `b05613b5`. It is one of 28 commits in that deploy.
- The first Monday after that deploy was 08-18, and that's the first missed reminder.

**Unrelated noise**

Before the deploy, the logs show `datetime - NoneType` errors from a missing `stable_at` or `triage_at`. Those were fixed separately in `32fa810f` and aren't the cause here.

**Fix**

Compare against `calendar.MONDAY` using `date.today().weekday()`, or go back to `isoweekday() == 1`. I'd also add a test that the helper returns true on a Monday. Want me to make that change?

----- next turn -----

The weekly Monday reminders are fixed. The new tests pass with the fix and fail without it.

**Cause:** `_is_reminder_day()` compared `date.today().isoweekday()` to `calendar.MONDAY`. `isoweekday()` counts Monday as 1, but `calendar.MONDAY` is 0, so the check was never true. Commit c509d45e refactored the inline `isoweekday() == 1` check into this helper and introduced the mismatch. The helper is shared by `case_close_reminder` (triage cases) and `case_stable_reminder` (stable cases), so both stopped sending.

**Fix:** the helper in `src/dispatch/case/scheduled.py` now uses `weekday()`, which is 0 for Monday.

**Regression test:** `tests/case/test_case_scheduled.py` has 11 tests. They check that:
- `_is_reminder_day()` is true only on a Monday.
- Both the triage and stable reminder tasks send on a Monday and don't send on a Tuesday, for cases older than a week.

**Evidence from the scheduler log:**
- Close reminders were sent on Mondays 2025-07-28, 08-04 and 08-11.
- The scheduler on image `main-81d8ae42` started on Wed 2025-08-13, and c509d45e is in that image but not in the earlier `main-b05613b5`.
- No reminders went out on Monday 2025-08-18.
- The scheduler log's error lines (a `NoneType` subtraction in the same two task functions) predate the refactor, so they aren't the cause.

I did not run the full suite, only the new test file.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e97f4eeacf950450c142ee27da8fcda3f
DEPLOYED_IMAGE: registry.example.com/dispatch:main-81d8ae42
FIRST_MISSED: 2025-08-18