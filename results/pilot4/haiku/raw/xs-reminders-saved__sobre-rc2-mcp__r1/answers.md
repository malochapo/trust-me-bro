**Root cause:** commit `c509d45e` ("refactor(case): share the weekly reminder check", Jordan Lee, 2025-08-12) changed the Monday check so it can never be true.

- **Before:** `date.today().isoweekday() == 1`. `isoweekday()` returns 1 for Monday.
- **After:** `_is_reminder_day()` returns `date.today().isoweekday() == calendar.MONDAY`. `calendar.MONDAY` is `0`, since Python's `calendar` numbers weeks from Monday = 0. I checked this in the sandbox: `calendar.MONDAY` is 0 and the Monday 2025-08-11 date gives `isoweekday()` of 1, so the comparison is False on every day.

`_is_reminder_day()` is used by both `case_close_reminder` (`src/dispatch/case/scheduled.py:49`) and `case_stable_reminder` (line 95). That is why both the triage-close and stable reminders stopped. The daily triage reminder (`case_triage_reminder`) doesn't call `_is_reminder_day()`, so it still fires.

**Log evidence:**
- The last "Case close reminder sent" entries are on Monday 2025-08-11 (`scheduler.log:16801`–`16808`), which was before the bad commit.
- Monday 2025-08-18 has no close or stable reminder sends. The only Monday send is an incident close reminder, which doesn't use this code path (`scheduler.log:25284`).
- Daily triage reminders keep going out through this period, consistent with the code.

**Deploy that shipped it:** image `registry.example.com/dispatch:main-81d8ae42`. Its startup is logged on the scheduler at `2025-08-13T16:40:06Z` (`scheduler.log:18851`) and on the web tier at `16:40:07Z` (`api.log:13201`). `c509d45e` is an ancestor of `81d8ae42`, and `b05613b5` (the image running before, from 2025-07-30) doesn't contain it. The first Monday after that deploy was 2025-08-18, which is when the reminders stopped.

**Other things I noticed, not part of this bug:**
- On 2025-08-20 `case_close_reminder` logs `unsupported operand type(s) for -: 'datetime.datetime' and 'NoneType'` at `scheduled.py:47` (`datetime.utcnow() - case.triage_at`). It's caught per case, so it doesn't stop the job, but cases with a null `triage_at` are skipped with an error. Worth a look separately.
- The stable-reminder `NoneType` error in July was fixed by `32fa810f` (2025-08-11), which the scheduler picked up in this same deploy window.

No code changed. For the fix, the minimal option is to compare with `date.today().weekday() == calendar.MONDAY` (or `isoweekday() == 1`), and add a test that patches the date to a Monday, since nothing currently exercises `_is_reminder_day()`.

----- next turn -----

I saved the findings to project memory so tomorrow's session can pick them up:

- **File:** `memory/case-weekly-reminder-monday-bug.md`
- **Index:** a pointer line added to `MEMORY.md`

The note covers:
- **Root cause:** commit `c509d45e` compares `isoweekday()` to `calendar.MONDAY`, which is 0, so the Monday check is never true. It affects `case_close_reminder` and `case_stable_reminder` in `src/dispatch/case/scheduled.py`.
- **Deploy:** image `main-81d8ae42`, started 2025-08-13 16:40Z. The last good Monday sends were 2025-08-11 and the first broken Monday was 2025-08-18.
- **Fix, not applied:** use `weekday() == calendar.MONDAY` (or `isoweekday() == 1`) and add a Monday-date test.
- **Separate issue:** a NoneType error on `case.triage_at` in `case_close_reminder` on 2025-08-20.

No code was changed in this session.

----- next turn -----

Fixed the weekday bug, added a regression test, and the test suite for `tests/case` passes (19 passed). The change is uncommitted in the working tree.

**What was wrong:** Commit `c509d45e` replaced `date.today().isoweekday() == 1` with a shared helper, `_is_reminder_day()`, that compared `isoweekday()` against `calendar.MONDAY`. `isoweekday()` returns 1 for Monday, but `calendar.MONDAY` is 0, so the check was never true. Both `case_close_reminder` and `case_stable_reminder` depend on it, so the weekly reminders stopped. Triage reminders are not affected.

**Fix:** `src/dispatch/case/scheduled.py` now uses `date.today().weekday() == calendar.MONDAY`. Both sides are 0-based, so Monday matches.

**Regression test:** `tests/case/test_case_scheduled.py` patches `date` and checks `_is_reminder_day()` on a Monday, Sunday, Tuesday, and Friday. I ran it before the fix and the Monday case failed, which confirms it catches the bug.

**Evidence from the logs:** Monday 2025-08-11 still sent close and stable reminders on the old image. On Monday 2025-08-18 the scheduler ran both jobs with no sends. The `main-81d8ae42` image had been running since 2025-08-13.

**Not done:**
- I did not commit, since you didn't ask for one.
- I did not run the full test suite, only `tests/case`.
- `case_close_reminder` also logs a `NoneType` error on `case.triage_at` every day, including 2025-08-18. Those cases are skipped. This is a separate problem and I did not change it.
- I updated the memory note to reflect that the fix is applied.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e97f4eeacf950450c142ee27da8fcda3f
DEPLOYED_IMAGE: main-81d8ae42
FIRST_MISSED: 2025-08-18