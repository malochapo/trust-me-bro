I have the root cause and the deploy. I did not change any code.

**Root cause:** commit `c509d45e` ("refactor(case): share the weekly reminder check", 2025-08-12) added `_is_reminder_day()` in `src/dispatch/case/scheduled.py`. It returns `date.today().isoweekday() == calendar.MONDAY`.

- `isoweekday()` numbers Monday as 1 and Sunday as 7.
- `calendar.MONDAY` is 0, because the `calendar` module numbers weekdays from 0.
- The comparison can therefore never be true.

Before the refactor, both `case_close_reminder` (long-running triage cases) and `case_stable_reminder` (stable cases) checked `isoweekday() == 1`, which was correct. The refactor swapped that literal for the helper, so both weekly reminders stopped sending. `case_triage_reminder` has no Monday check, which is why the daily triage reminders kept arriving.

**Deploy that shipped it:** image `registry.example.com/dispatch:main-81d8ae42`, which includes `c509d45e` as an ancestor.

- It started on the scheduler pod `scheduler-mhtsgqwwx-q5q2n` at 2025-08-13T16:40:06Z.
- It started on the web pod at 16:40:07Z.
- The previous image, `main-b05613b5`, dates from 2025-07-29 and does not contain the commit.

**Log evidence (Mondays, 18:00 run):**

| Date | Image | "Case close reminder sent" lines |
|---|---|---|
| 07-28 | `main-b05613b5` | 5 |
| 08-04 | `main-b05613b5` | 7 |
| 08-11 | `main-b05613b5` | 6 |
| 08-18 | `main-81d8ae42` | 0 |

- On 08-18 `case_stable_reminder` ran cleanly and sent nothing.
- On 08-18 `case_close_reminder` logged only the `None` `triage_at` error, which is a separate issue (see below).
- The single "close reminder sent" line on 08-18 is `Incident close reminder sent to l.nguyen@example.com`, from the incident job, not the case one.

**Unrelated issue:** both case jobs log `TypeError: datetime - NoneType` for some cases on every run, including before the deploy. In `case_close_reminder` it comes from `case.triage_at` being `None`. A try/except inside the loop catches it per case, so it isn't the cause here. Commit `32fa810f` already guards `stable_at`, but `triage_at` is still unguarded.

**Suggested fix when you want it:**
- Compare against `calendar.MONDAY` using `date.today().weekday()`, or compare `isoweekday()` to 1.
- Add a test that fakes a Monday and a Tuesday.
- Guard `triage_at` against `None`.

Reminders skipped since 08-18 won't be sent retroactively.

----- next turn -----

Fixed, and the new test fails without the fix.

**Fix:** in `src/dispatch/case/scheduled.py`, `_is_reminder_day()` now uses `date.today().weekday() == calendar.MONDAY`. `weekday()` and `calendar.MONDAY` both number Monday as 0, so the check matches again.

**Regression test:** `tests/case/test_case_scheduled.py`
- It checks `_is_reminder_day()` on a Monday, a Tuesday, a Wednesday and a Sunday.
- It runs the real `case-stable-reminder` and `case-close-reminder` job bodies. It uses a 10-day-old case and a fake date, and asserts a reminder goes out on Monday and not on Tuesday.
- With the fix, all 8 tests pass.
- With the fix reverted, 3 of the 8 fail: the Monday cases for the helper and for both jobs.

I only ran the new test file, not the whole suite.

I left the separate `triage_at is None` error in `case_close_reminder` alone, since you only asked for this fix. Nothing is committed. Once this is deployed, the next Monday run should send the reminders again.

----- next turn -----

The nightly TypeError is fixed. Cases in triage with no `triage_at` now get their weekly reminder, counted from `created_at`. All 10 tests in `tests/case/test_case_scheduled.py` pass. I ran only that file, not the whole suite.

**Cause:** `case_close_reminder` computed `datetime.utcnow() - case.triage_at`. `triage_at` is only filled in by `case_triage_status_flow` (`src/dispatch/case/flows.py:592`), and the column is nullable. A case that is in triage status but never went through that flow has it empty. The subtraction then fails with `datetime - None`. The per-case `try/except` swallowed the error, so those cases were logged every evening and never reminded, even on Mondays. I didn't look in the database, so I haven't confirmed why those particular cases lack the timestamp. The logs only show that some triage cases do.

**Fix:** in `src/dispatch/case/scheduled.py`, the job now uses `case.triage_at or case.created_at` as the start of the span.

**Test:** `test_close_reminder_falls_back_to_created_at_without_triage_at` uses a triage case with no `triage_at` on a Monday.
- A 10-day-old case gets a reminder and a 3-day-old one doesn't.
- It also asserts nothing is logged as an exception.

I checked it by temporarily reverting the source changes. The new test fails without the fix, but that revert also undid the earlier Monday fix, so the failures aren't cleanly separated.

I left `case_stable_reminder` alone. It skips cases with no `stable_at` (from #6179) rather than falling back, so stable cases missing that timestamp still never get a reminder. Say if you want the same fallback there. Nothing is committed.

----- next turn -----

**Recap**

- **Symptom:** since mid-August, assignees stopped getting the Monday reminders for long-running triage and stable cases. The daily triage reminders kept arriving because that job has no Monday check.
- **Root cause:** commit `c509d45e` ("refactor(case): share the weekly reminder check", 2025-08-12) added `_is_reminder_day()`, which compared `date.today().isoweekday()` to `calendar.MONDAY`. `isoweekday()` numbers Monday as 1, while `calendar.MONDAY` is 0, so the check never matched and both weekly jobs went silent.
- **Deploy:** image `main-81d8ae42` started on the scheduler and web pods on 2025-08-13 at about 16:40Z. The previous image, `main-b05613b5`, does not contain the commit.
- **Evidence:** the Monday 18:00 runs sent 5, 7 and 6 case close reminders on 07-28, 08-04 and 08-11. On 08-18, the first Monday after the deploy, they sent none.
- **Fix (uncommitted):** `_is_reminder_day()` now uses `weekday()`, which also numbers Monday as 0. A regression test runs the real jobs on a faked Monday and Tuesday.
- **Second issue:** `case_close_reminder` logged a `datetime - None` TypeError every evening. `triage_at` is only set by the triage transition flow, so triage cases that never went through it have none, and the error stopped those cases getting reminders. The job now falls back to `created_at`, with a test. I haven't confirmed in the database why those cases lack `triage_at`.
- **Not covered:** reminders missed since 08-18 won't be sent retroactively. `case_stable_reminder` still skips stable cases that have no `stable_at`, with no fallback. I ran only the new test file, not the whole suite, and nothing is committed.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e
DEPLOYED_IMAGE: main-81d8ae42
FIRST_MISSED: 2025-08-18
MISSING_FIELD: triage_at