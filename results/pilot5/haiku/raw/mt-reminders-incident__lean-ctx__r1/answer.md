**Recap**

- **Weekday bug:** commit `c509d45e` (2025-08-12, "refactor(case): share the weekly reminder check") replaced the working `isoweekday() == 1` with `isoweekday() == calendar.MONDAY`. `calendar.MONDAY` is 0, so the check never passed and the weekly close and stable reminders for long-running cases never went out.
- **Deploy:** the first production rollout containing that commit was `main-81d8ae42`, which started on the scheduler and web pods on 2025-08-13 at 16:40 UTC. The previous deploy, `main-b05613b5`, didn't include it.
- **First missed Monday:** 2025-08-18. The 2025-08-11 run was before the deploy and used the old code, so it's not counted as missed. The logs don't record reminder sends, so this date is inferred from the deploy timing and the code.
- **Evening TypeError:** `case_close_reminder` computed `datetime.utcnow() - case.triage_at`. Some triage cases have `triage_at` as `NULL`, and the per-case `try/except` logged the error and skipped them. Two paths can leave it null: the dispatcher's `(_, triage)` branch and `reopen_button_click`. I haven't confirmed which one produced the rows in production.
- **Fixes (uncommitted in the working tree):**
  - `_is_reminder_day` now uses `weekday()`.
  - The close reminder falls back to `created_at` when `triage_at` is missing.
  - Regression tests are in `tests/case/test_case_scheduled.py`. The 10 tests pass, and I confirmed each one fails against the bug it guards. The full suite has the same 8 failures as the untouched base (`ai`, `database`, `entity`), so they predate this work.
- **Not addressed:** the null `triage_at` writes still happen, and `case_stable_reminder` still silently skips cases with no `stable_at`.

```
FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e97f4eeacf950450c142ee27da8fcda3f
DEPLOYED_IMAGE: main-81d8ae42
FIRST_MISSED: 2025-08-18
MISSING_FIELD: triage_at
```