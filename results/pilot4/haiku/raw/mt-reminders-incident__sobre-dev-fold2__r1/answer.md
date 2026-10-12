## Recap

**Weekday bug.** Commit `c509d45e` ("refactor(case): share the weekly reminder check", 2025-08-12) moved the Monday check into `_is_reminder_day()`, which compared `date.today().isoweekday()` against `calendar.MONDAY`. ISO weekdays number Monday as 1, but `calendar.MONDAY` is 0, so the check was never true. Both weekly close reminders (long-running triage and stable cases) stopped. The daily triage reminders don't use this check and kept sending. The fix compares `date.today().weekday()` to `calendar.MONDAY`. The regression test in `tests/case/test_case_scheduled.py` fails on the old comparison and passes on the fix.

**Deploy.** `c509d45e` shipped in `main-81d8ae42`. The scheduler started that image at 2025-08-13T16:40Z. The Monday before the deploy (2025-08-11) still sent close reminders. The first Monday without them was 2025-08-18.

**Evening TypeError.** `case_close_reminder` computed `datetime.utcnow() - case.triage_at`. Some triage cases have `triage_at` set to NULL, so the subtraction raised a TypeError. The job catches the error per case, so it logged one each evening (40 in the logs) without stopping the run. The fix counts from `case.created_at` when `triage_at` is missing. Three tests cover it: a case with no `triage_at` created 8 days ago gets the reminder, one created 2 days ago doesn't, and a case with `triage_at` set uses that value.

**Not changed:** `case_stable_reminder` has no TypeError because it already skips cases with no `stable_at`, so those cases get no weekly reminder. The fixes are uncommitted. The full suite has 8 failures in AI service, one database test, and one entity test, and they fail the same way on the original commit.

```
FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e97f4eeacf950450c142ee27da8fcda3f
DEPLOYED_IMAGE: main-81d8ae42
FIRST_MISSED: 2025-08-18
MISSING_FIELD: triage_at
```