The weekly Monday reminders are dead because of an off-by-one in the weekday check, introduced by commit `c509d45e` and shipped in deploy `main-81d8ae42`. I haven't changed any code.

**Root cause**

`src/dispatch/case/scheduled.py:31-33`, added in `c509d45e`:

```python
def _is_reminder_day() -> bool:
    return date.today().isoweekday() == calendar.MONDAY
```

`isoweekday()` returns 1 for Monday, but `calendar.MONDAY` is 0 in Python. I confirmed both values locally: `calendar.MONDAY = 0`, and `date(2025,8,18).isoweekday() = 1`. So `_is_reminder_day()` is always False, and the weekly branch never sends.

The old code was `date.today().isoweekday() == 1`, which was correct. The refactor replaced the literal with `calendar.MONDAY`, which broke it. Both callers use this helper:
- `case_stable_reminder` (line 95): the stable-case reminder you're missing.
- `case_close_reminder` (line 49): the long-running triage reminder.

The daily triage reminders (`case_triage_reminder`) don't use this check, which is why they still arrive.

**The deploy**

- `c509d45e` (Jordan Lee, 2025-08-12 14:05 -0700) introduced the bug.
- `81d8ae42` (David Whittaker, 2025-08-12 14:47 -0700) is the HEAD that was deployed. It contains `c509d45e`.
- The scheduler log shows the new container `scheduler-mhtsgqwwx` starting on `registry.example.com/dispatch:main-81d8ae42` at 2025-08-13T16:40:06Z.
- The last Monday before the deploy, 2025-08-11, ran the old code. The first Monday after it, 2025-08-18, ran `case_stable_reminder` with no error and no reminders sent.

**A separate issue in the same logs**

From 2025-07-28 to 2025-08-12, `case_stable_reminder` crashed nightly with `unsupported operand type(s) for -: 'datetime.datetime' and 'NoneType'` on `case.stable_at`, which stopped the job for the cases after the failing one. Commit `32fa810f` (2025-08-11, "not all cases have a stable_at date") fixes this. It is already in `81d8ae42`, and the errors stop after the 08-13 deploy. So the crash is resolved, but it is worth knowing it existed in the same window.

**Suggested fix (not applied)**

Change `_is_reminder_day()` to compare against 1, or use `isoweekday() == 1` directly, and add a regression test that mocks Monday and checks both reminder functions send. I haven't written that test.

I also recorded this finding in sobre's session log.

----- next turn -----

I saved the findings to the project memory, with an index line in `MEMORY.md`. The finding is also in the sobre session log from earlier.

Tomorrow you can pick up from there:
- **Root cause:** `_is_reminder_day()` in `src/dispatch/case/scheduled.py` compares `isoweekday()` (Monday = 1) with `calendar.MONDAY` (= 0), so the weekly reminders never send. This came from `c509d45e` and shipped in `81d8ae42`, which the scheduler started on 2025-08-13 at 16:40 UTC.
- **Fix, not applied:** compare to 1, and add a regression test that mocks a Monday and checks both reminders send.
- **Already fixed separately:** the nightly `stable_at` = None crash, fixed by `32fa810f`.

No code has been changed.

----- next turn -----

The weekday bug is fixed and covered by a regression test. The reminders should go out again on the next Monday the scheduler runs.

**Cause:** `_is_reminder_day()` in `src/dispatch/case/scheduled.py` compared `date.today().isoweekday()` (Monday = 1) with `calendar.MONDAY` (Monday = 0). The comparison was always False, so no weekly reminder was ever sent. Both `case_close_reminder` and `case_stable_reminder` call this helper, so both were affected.

**Fix:** `date.today().weekday() == calendar.MONDAY`. `weekday()` is 0-based like `calendar.MONDAY`.

**Regression test:** `tests/case/test_case_scheduled.py` pins `date.today()` to each day of one week and checks `_is_reminder_day()` returns True only on Monday. The Monday case fails on the old code and passes on the fix. `python -m pytest tests/case` passes (22 tests). I did not run the full suite.

**Log evidence:** The Monday 2025-08-11 run was on image `main-b05613b5`, before the bug, and sent 5 close reminders. The first Monday on `main-81d8ae42` was 2025-08-18, and the logs show no reminder sends for it. The scheduler started on `main-81d8ae42` at 2025-08-13T16:40:06Z. The logs end around 2025-08-20, so I could not check later Mondays.

**Choices I made:**
- Fixed the helper rather than each caller, since both reminders share it.
- Left the project memory note saying "fix pending" unchanged. It is now stale.
- Did not commit. Changes are in the working tree: the one-line fix and the new test file.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e
DEPLOYED_IMAGE: main-81d8ae42
FIRST_MISSED: 2025-08-18