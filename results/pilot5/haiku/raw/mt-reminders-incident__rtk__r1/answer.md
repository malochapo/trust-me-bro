Here's the recap for the incident report.

**Summary**

- **Weekly reminders stopped after the 2025-08-13 production deploy.** The Monday close and stable reminders never sent again. Daily triage reminders kept working because they don't use the weekday gate.
- **Root cause:** commit `c509d45e` ("refactor(case): share the weekly reminder check", 2025-08-12) moved the Monday check into `_is_reminder_day()`, which compares `date.today().isoweekday()` against `calendar.MONDAY`. `isoweekday()` numbers Monday as 1, but `calendar.MONDAY` is 0, so the check was always false. The old inline check compared against `1` and was correct.
- **Deploy:** the rollout at 2025-08-13 16:40Z (09:40 PT) replaced both the scheduler and API pods. Their logs show the image `registry.example.com/dispatch:main-81d8ae42`, and `c509d45e` is an ancestor of `81d8ae42`, so the deployed build contains the bug.
- **Fix:** `_is_reminder_day()` compares against `1` with a comment explaining the numbering, and the unused `calendar` import is removed. A regression test covers all seven weekdays and both reminder jobs end to end.
- **Separate evening TypeError:** `case_close_reminder` subtracted `case.triage_at` from the current time, and `triage_at` is `NULL` for some cases in triage. The reopen button and the status dispatcher's catch-all branch don't stamp it, and cases triaged before the column existed would also be `NULL`. The job now counts from `created_at` when `triage_at` is missing, with tests for both the 8-day and 2-day cases.
- **Test status:** the full suite has 8 failures in AI, database, and entity tests. They also fail on the original code, so they predate this work.

**Caveats for the report**

- The logs don't record when reminders are sent, so `FIRST_MISSED` comes from the code and the deploy timing, not from observed missing sends. The 2025-08-11 Monday ran on the old pod and old code, so it would have sent.
- The `TypeError` also ran through the stable-reminder path until the `stable_at` guard shipped in `32fa810f`, so the stable-reminder errors in the logs stop around the 08-11 fix, not at the 08-13 deploy.

```
FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e97f4eeacf950450c142ee27da8fcda3f
DEPLOYED_IMAGE: registry.example.com/dispatch:main-81d8ae42
FIRST_MISSED: 2025-08-18
MISSING_FIELD: triage_at
```