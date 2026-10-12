**Recap**

- **Weekday bug:** `_is_reminder_day()` in `src/dispatch/case/scheduled.py` compared `date.today().isoweekday()` (Monday = 1) against `calendar.MONDAY` (Monday = 0). The comparison was never true, so the weekly close and stable reminders never went out. The triage reminders are daily and don't use this check, so they were unaffected.
- **Introduced by:** commit `c509d45e` (2025-08-12, "refactor(case): share the weekly reminder check"). It replaced an inline check that compared against the literal `1`, which was correct.
- **Shipped:** image `registry.example.com/dispatch:main-81d8ae42`, started on the scheduler at 2025-08-13 16:40 UTC. The previous image, `main-b05613b5`, predates the refactor.
- **Impact:** the Monday 2025-08-11 run, before the deploy, sent its reminders. The first Monday missed was 2025-08-18, and the job ran that day with zero close or stable sends.
- **Fix and tests:** `weekday()` replaces `isoweekday()`. The new tests in `tests/case/test_case_scheduled.py` fail with the bug restored and pass with the fix.
- **Evening TypeError:** `case_close_reminder` subtracted `case.triage_at`, which is `NULL` for some cases in triage. The error is caught per case, so those cases were skipped and never got their reminder. I changed the job to count from `case.created_at` when `triage_at` is missing. The exact path that leaves `triage_at` empty isn't confirmed; the logs don't name the cases.
- **Not committed:** all changes are in the working tree.

```
FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e
DEPLOYED_IMAGE: main-81d8ae42
FIRST_MISSED: 2025-08-18
MISSING_FIELD: triage_at
```