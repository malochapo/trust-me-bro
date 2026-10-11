Recap for the incident report:

**Symptom.** Since mid-August, assignees stopped getting the weekly Monday reminders for long-running triage and stable cases. Daily triage reminders kept arriving, and nobody changed the reminder settings.

**Root cause.** Commit `c509d45e` (Aug 12, "refactor(case): share the weekly reminder check") moved the Monday test into `_is_reminder_day()`, which compared `date.today().isoweekday()` (1 for Monday) with `calendar.MONDAY` (0 in Python). The comparison was never true, so `case_close_reminder` and `case_stable_reminder` never sent. The daily triage reminder doesn't use this check, so it kept working. The fix changes the call to `date.today().weekday()`, which is 0-based like `calendar.MONDAY`. A regression test in `tests/case/test_case_scheduled.py` pins each weekday and fails on the old code for Monday.

**Deploy.** The scheduler restarted on 2025-08-13 at 16:40 UTC with image `main-81d8ae42`, which is `main` at that point and contains `c509d45e`. The web pod got the same image. The previous scheduler image, `main-b05613b5`, still sent reminders on Monday 2025-08-11.

**Impact.** The first missed Monday was 2025-08-18. The logs show no close or stable reminders that day, and none since.

**Evening TypeError.** `case_close_reminder` computed `datetime.utcnow() - case.triage_at`. Some cases reach triage without `triage_at` being set. `triage_at` is only set in `case_triage_status_flow`, and the Slack reopen handler (`reopen_button_click`) assigns `CaseStatus.triage` directly without running that flow. The job logged the TypeError for each such case and skipped it, so those cases never got a weekly reminder. The fix counts from `created_at` when `triage_at` is missing. Three tests cover the fallback, a recent case that should not be reminded, and the case where `triage_at` is set. I haven't confirmed which production cases lack `triage_at`.

**Separate issue.** `case_stable_reminder` was also failing daily from 2025-07-28 on cases with no `stable_at`. Commit `32fa810f` (Aug 11) added the guard.

**Status.** Both fixes are uncommitted in the working tree. The full suite has 8 failures in the AI, database and entity tests. They also fail without these changes.

```
FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e97f4eeacf950450c142ee27da8fcda3f
DEPLOYED_IMAGE: main-81d8ae42
FIRST_MISSED: 2025-08-18
MISSING_FIELD: triage_at
```