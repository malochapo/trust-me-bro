## Recap

**Weekly reminder bug.** `_is_reminder_day()` compared `date.today().isoweekday()` (Monday = 1) against `calendar.MONDAY` (Monday = 0). The check was never true, so the weekly close and stable reminders never sent. Triage reminders don't use this helper, so they kept firing daily. Commit `c509d45e` introduced the mismatch when it moved the check into the helper. It reached production in image `main-81d8ae42`, rolled out on 2025-08-13. The logs show close and stable reminders on Monday 2025-08-11, before the rollout, and none on Monday 2025-08-18.

**Fix.** The helper now uses `date.today().weekday()`, which matches `calendar.MONDAY`. `tests/case/test_case_scheduled.py` checks Monday through Sunday. It fails on the old code for Monday and passes with the fix.

**Evening `TypeError`.** `case_close_reminder` subtracted `case.triage_at` from the current time. `triage_at` is only set by the triage transition flow, so cases that reached triage through other paths had it null. The per-case `try`/`except` logged the error and moved on, so the other cases still got reminders. The job now counts from `created_at` when `triage_at` is missing. Three tests cover the fallback; removing it reproduces the logged `TypeError`. The case and case_cost suites pass (44 tests).

**Open items.**
- The logs don't name the affected cases, so I haven't confirmed which path produced the null `triage_at` values. The reopen button in `src/dispatch/plugins/dispatch_slack/case/interactive.py` sets triage directly and is a likely candidate.
- `case_stable_reminder` still skips cases with a null `stable_at` rather than falling back. That's a separate gap, which I haven't changed.
- Nothing is committed yet.

```
FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e97f4eeacf950450c142ee27da8fcda3f
DEPLOYED_IMAGE: main-81d8ae42
FIRST_MISSED: 2025-08-18
MISSING_FIELD: triage_at
```