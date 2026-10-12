## Recap

**Weekly reminders stopped because of one commit.** Commit `c509d45e` (Jordan Lee, 2025-08-12, "refactor(case): share the weekly reminder check") moved the Monday check into `_is_reminder_day()`. The old code compared `isoweekday()` (Monday = 1) to 1. The new code compared it to `calendar.MONDAY`, which is 0 in Python, so the check was never true. Weekly close and stable reminders were skipped on every day; daily triage reminders have no weekday check and kept going.

**Deploy:** the scheduler pod started on image `main-81d8ae42` (commit `81d8ae42`, which contains `c509d45e`) at 2025-08-13 16:40 UTC. The previous scheduler image, `main-b05613b5`, still sent reminders on Monday 2025-08-11 (5 close reminders). The next Monday, 2025-08-18, sent none, while triage reminders for that day went out.

**Evening TypeError:** `case_close_reminder` subtracted `case.triage_at` from `utcnow()`. `triage_at` is only set by the triage transition flow, so cases that reach triage without it (the Slack reopen button sets the status directly, for example) have it NULL, and the job raised `TypeError` each evening. The per-case `try/except` kept other cases going. The job now counts from `created_at` when `triage_at` is missing.

**Fixes and tests:**
- `src/dispatch/case/scheduled.py`: `_is_reminder_day()` now uses `date.today().weekday()`, and `case_close_reminder` falls back to `created_at`.
- `tests/case/test_case_scheduled.py` (new): tests for the weekday check across a week, the Monday-only behaviour of both weekly jobs, and the `created_at` fallback. I confirmed the Monday and fallback tests fail on the old code.
- Full suite: 8 failed, 372 passed, 4 skipped. The 8 failures (AI service, one database test, one entity test) also fail on the original code, so they predate this work.

**Open items:**
- The reopen button path that leaves `triage_at` NULL still exists. Routing it through the triage flow would stop new NULL rows.
- Stable reminders still skip cases with no `stable_at` rather than falling back to `created_at`.
- No changes are committed.

```
FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e
DEPLOYED_IMAGE: main-81d8ae42
FIRST_MISSED: 2025-08-18
MISSING_FIELD: triage_at
```