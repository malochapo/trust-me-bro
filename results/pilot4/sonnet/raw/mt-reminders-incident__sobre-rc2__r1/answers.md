**Root cause:** commit `c509d45e`, "refactor(case): share the weekly reminder check" (Jordan Lee, 2025-08-12), broke the Monday check. It was shipped to production by the 2025-08-13 deploy of image `dispatch:main-81d8ae42`.

**What the commit did.** It pulled the inline check `date.today().isoweekday() == 1` out of `case_close_reminder` and `case_stable_reminder` into a shared helper. The helper is at `src/dispatch/case/scheduled.py:31`:

```python
return date.today().isoweekday() == calendar.MONDAY
```

`calendar.MONDAY` is `0` (I confirmed this by running it), but `isoweekday()` returns 1 to 7, with Monday as 1. The comparison is never true, so both jobs skip every case on every day. They still run on schedule and raise no error. That is why only the weekly reminders went quiet. The daily triage reminder (`case_triage_reminder`) doesn't use the helper, so it kept working.

**Timeline from the logs** (the scheduler fires at 18:00 UTC):

| Date | Pod and image | Triage and stable "Case close reminder sent" lines |
|---|---|---|
| Mon 07-28 | `scheduler-46x2cb2h2` | Sent to several assignees |
| Mon 08-04 | `scheduler-xdp7k6gs2q`, `main-b05613b5` | Sent to several assignees |
| Mon 08-11 | `scheduler-xdp7k6gs2q`, `main-b05613b5` | Sent to several assignees |
| Wed 08-13, 16:40 UTC | `scheduler-mhtsgqwwx` and `web-5dkmr9s9s` start, image `main-81d8ae42` | Not applicable |
| Mon 08-18 | `scheduler-mhtsgqwwx`, `main-81d8ae42` | None sent |

- **Mon 08-18:** the triage-reminder job still sent to l.nguyen. `case_stable_reminder` finished in 0.03s, and `case_close_reminder` in 0.05s with no sends.
- **Line numbers:** the stack traces on 08-18 show `case_close_reminder` at line 47 instead of 43. That matches the 4 lines the refactor added, so the new code was running.
- **Deploy contents:** `81d8ae42` is the commit right after `c509d45e` on main (a later `git log` listing shows it just after `c509d45e`), so the image contains the refactor.
- **Why it wasn't visible:** the helper's `False` result looks like "no cases due", so nothing was logged.

**Unrelated noise, not the cause.** Every 18:00 run logs `unsupported operand type(s) for -: 'datetime' and 'NoneType'` in both jobs, both before and after the deploy. Some case has `triage_at` or `stable_at` set to None. The per-case try/except catches it and the loop continues. The "stable_at" part is probably the case commit `32fa810f` meant to guard, but `case_close_reminder` still has no `triage_at` guard. It's worth fixing separately.

**Suggested fix, not applied:** compare against `calendar.MONDAY + 1`, or better `date.today().weekday() == calendar.MONDAY`. A small unit test for `_is_reminder_day` that freezes a Monday date would have caught this. I haven't changed any code.

----- next turn -----

I fixed the Monday check and added a regression test. The new tests pass with the fix. With the fix reverted, the two Monday cases fail, which is the failure that would have caught the bug.

- **Fix:** in `src/dispatch/case/scheduled.py`, `_is_reminder_day()` now uses `date.today().weekday() == calendar.MONDAY`. `weekday()` counts Monday as 0, which matches `calendar.MONDAY`. The old `isoweekday()` counts Monday as 1, so the comparison could never be true.
- **Tests:** the new file is `tests/case/test_case_scheduled.py`.
  - It checks `_is_reminder_day()` for each day of a week starting Monday 2025-08-18. Only Monday should return true.
  - It runs the real `case_close_reminder` job, with the case lookup and the send call mocked. A case that has been in triage for 10 days gets a reminder on Monday and none on Tuesday.
- **Not covered:** `case_stable_reminder` has no test of its own. It uses the same helper, so the helper test covers the bug, but a job-level test for it would be a quick addition.

I only ran the new test file, not the full suite, and I haven't committed anything.

The separate `triage_at` / `stable_at` is `None` error from the logs is still unfixed. `case_close_reminder` has no guard for a missing `triage_at`. I left it alone because it's outside this fix, but I can add the guard if you want.

----- next turn -----

Fixed, and the new test passes. The close reminder now counts from `case.triage_at`, or from `case.created_at` when `triage_at` is missing. With the source changes reverted, the new test fails, and so do the two Monday tests from the earlier fix.

**Cause of the TypeError.** `case_close_reminder` computed `datetime.utcnow() - case.triage_at`, and `triage_at` is `None` for some triage-status cases. Code only sets `triage_at` in `case_triage_status_flow` (`src/dispatch/case/flows.py:594`), when a case moves into triage. A case that never went through that transition has no `triage_at`. That includes cases created directly in triage status, and likely cases that predate the transition code, though I couldn't confirm that from the logs.

**Why it logged every evening.** The subtraction ran before the Monday check, so it raised for each such case every day. The per-case try/except caught it and logged it. On Mondays those cases were skipped without a reminder, even before the `calendar.MONDAY` bug. The traceback appears in the 07-28 logs.

**Fix.** The change is at `src/dispatch/case/scheduled.py:47`, with a short comment explaining it.

**Test.** `test_case_close_reminder_counts_from_created_at_without_triage_at` runs the job on a Monday with two cases that have no `triage_at`. The case created 10 days ago gets a reminder, the one created 2 days ago doesn't, and nothing is logged as an exception. I ran only this test file, not the full suite, and nothing is committed.

**Stable-case job not changed.** `case_stable_reminder` skips cases with no `stable_at`, and I left that as is. You only asked about the close reminder job, and `created_at` doesn't mean much for a case that went stable later. If you want the same fallback there, tell me what date it should count from.

----- next turn -----

## Recap

**Symptom:** since mid-August, assignees stopped getting the weekly Monday reminders to close long-running triage and stable cases. The daily triage reminders kept arriving.

**Weekday bug**
- Commit `c509d45e` (2025-08-12, "refactor(case): share the weekly reminder check") moved the inline Monday check into a helper, `_is_reminder_day()`.
- The helper compared `date.today().isoweekday()` with `calendar.MONDAY`. `isoweekday()` counts Monday as 1, but `calendar.MONDAY` is 0, so the check was never true.
- Both weekly jobs, `case_close_reminder` and `case_stable_reminder`, skipped every case on every day. Nothing was logged, because skipping looks the same as having nothing to send.
- The daily triage reminder doesn't use the helper, so it kept working.
- The scheduler pod started on image `main-81d8ae42` on 2025-08-13 at 16:40 UTC, and the web pod started on the same image seconds later. That image includes the refactor.
- Monday 08-11 ran on the old image (`main-b05613b5`) and sent reminders. Monday 08-18 ran on the new image and sent none.
- The fix is to use `weekday()`, which counts Monday as 0 and matches `calendar.MONDAY`.

**Evening TypeError**
- `case_close_reminder` subtracted `case.triage_at` from the current time. `triage_at` is only set when a case moves into triage through `case_triage_status_flow`, so other triage cases have none.
- The error was caught and logged per case on every 18:00 run, and those cases never got a weekly reminder.
- The fix counts from `created_at` when `triage_at` is missing.
- The stable-case job still skips cases without `stable_at`.

**Code changes**
- Both fixes are in `src/dispatch/case/scheduled.py`.
- The tests are in `tests/case/test_case_scheduled.py`.
- I ran only that test file, not the full suite, and nothing is committed or deployed. Production keeps missing the Monday reminders until a build with these changes ships.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e
DEPLOYED_IMAGE: main-81d8ae42
FIRST_MISSED: 2025-08-18
MISSING_FIELD: triage_at