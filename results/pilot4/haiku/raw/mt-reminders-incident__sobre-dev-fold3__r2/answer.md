Here is the recap for the incident report. I haven't changed any code since the last fix, and the six lines at the end are the values you asked for.

**Summary**

- **Symptom:** assignees stopped getting the Monday reminders to close long-running triage and stable cases. The daily triage reminders kept arriving, and nobody changed the settings.
- **Root cause:** in `_is_reminder_day()`, the weekday check compared `date.today().isoweekday()` (Monday = 1) against `calendar.MONDAY` (Monday = 0). The check was never true, so both Monday jobs silently skipped every case.
- **How it was introduced:** commit `c509d45e` (Jordan Lee, 2025-08-12, "refactor(case): share the weekly reminder check") moved the check into the helper and used `calendar.MONDAY`. The old literal `1` was correct.
- **Deploy:** the scheduler restarted on image `main-81d8ae42` at 2025-08-13 16:40 UTC, and the Monday 2025-08-18 run was the first to skip sends. I'm inferring that the tag matches commit `81d8ae42` from the naming; I didn't check the registry.
- **Evidence:** Monday runs on 07-28, 08-04 and 08-11 sent close reminders. The 08-18 run sent none.
- **Fix:** `weekday() == calendar.MONDAY`. I've also changed the triage path to count from `created_at` when `triage_at` is missing. Regression tests are in `tests/case/test_case_scheduled.py`. The 17 tests in that file pass, and the 32 in `tests/case` pass.

**Secondary issue:** the evening TypeError came from triage cases with no `triage_at`. `triage_at` is set only in `case_triage_status_flow`, which runs on New→Triage and Closed→Triage. A case created directly in Triage, or moved from Stable or Escalated into Triage, never gets it. The Monday send wasn't blocked by this, since the per-case `try` caught the error, but it logged every night.

**Still open:**

- Stable cases with no `stable_at` are still skipped rather than counted from creation. I only changed the triage path.
- Setting `triage_at` in `service.create` and in the `(_, Triage)` branch would address the root of the secondary issue.

```
FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e97f4eeacf950450c142ee27da8fcda3f
DEPLOYED_IMAGE: main-81d8ae42
FIRST_MISSED: 2025-08-18
MISSING_FIELD: triage_at
```