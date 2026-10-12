## Recap

**Weekly reminders stopped after the 2025-08-13 deploy.** The weekday check in `_is_reminder_day()` compared `date.today().isoweekday()` (Monday = 1) with `calendar.MONDAY` (Monday = 0), so it was never true. The refactor that introduced this was `c509d45e`. It shipped in `main-81d8ae42`, which started on the scheduler and web containers at 2025-08-13 16:40 UTC. The Monday 2025-08-11 run was still on the earlier image and sent case close reminders. The 2025-08-18 run sent none. The daily triage reminders were not affected.

**Fix:** `_is_reminder_day()` now uses `weekday()`, which matches `calendar.MONDAY`. A new test, `tests/case/test_case_scheduled.py`, pins the helper to each day of one week. It fails on the old comparison.

**Evening TypeError:** `case_close_reminder` subtracted `case.triage_at` without a guard. Some Slack paths set a case to triage directly and skip `case_triage_status_flow`, which is the only place that sets `triage_at`. Those cases raised the error every evening, so they never received a reminder. The job now counts from `created_at` when `triage_at` is empty. A new test covers a case with no `triage_at` created 8 days ago (reminded) and one created 2 days ago (not reminded).

**Test results:** the new tests pass (9 in the file). The full suite has 368 passed, 4 skipped and 8 failed. The 8 failures are in AI service, database filter and entity service tests. They also fail without these changes.

**Open items:**
- `case_stable_reminder` still skips stable cases with no `stable_at` rather than counting from a fallback. Those cases get no reminder. This is a candidate follow-up, not part of this fix.
- The first-missed date is inferred from logs: the 2025-08-18 run logged no case close reminders, while 07-28, 08-04 and 08-11 each did. The log message is the same for triage and stable reminders, so this can't separate the two.
- No commit has been made. The changes are in the working tree.

```
FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e
DEPLOYED_IMAGE: main-81d8ae42
FIRST_MISSED: 2025-08-18
MISSING_FIELD: triage_at
```