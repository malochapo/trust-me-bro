Here's the recap for the incident report.

**Summary**

Since the Monday 2025-08-18 run, the weekly close reminders (for cases in triage and cases marked stable) have not been sent. The daily triage reminders kept arriving, which is why the change was easy to miss.

**Root cause**

Commit `c509d45e` (Jordan Lee, 2025-08-12, "refactor(case): share the weekly reminder check") moved the Monday check into `_is_reminder_day()`, which compared `date.today().isoweekday()` (Monday is 1) against `calendar.MONDAY` (Monday is 0). The comparison was never true, so both weekly reminder jobs stopped sending. The original code compared against `1`, which was correct.

**Deploy**

Image `registry.example.com/dispatch:main-81d8ae42` went out to the scheduler and web pods on 2025-08-13 at 16:40 UTC. Commit `c509d45e` is an ancestor of that commit. The last Monday with sends was 2025-08-11, which ran on the previous image (`main-b05613b5`).

**Evening TypeError**

The triage close-reminder job logged `TypeError: unsupported operand type(s) for -: 'datetime.datetime' and 'NoneType'` every evening, from 2025-07-28 onward. Cases in Triage with no `triage_at` caused it. `triage_at` is set only by `case_triage_status_flow`, and the status dispatcher's catch-all branch for transitions into Triage never calls it. The 2022 migration that added the column also didn't backfill it. I could not confirm which path produced the null rows in production, because the "Unexpected previous state" warning doesn't appear in either log file.

**Fixes and tests (uncommitted)**

- `src/dispatch/case/scheduled.py`:
  - `_is_reminder_day()` now uses `date.today().weekday()`, which is 0-based like `calendar.MONDAY`.
  - `case_close_reminder` counts from `triage_at or created_at`, so cases with no triage timestamp still get their weekly reminder.
- `tests/case/test_case_scheduled.py` (new, 10 tests):
  - The weekday check, Monday and each other day.
  - The reminder job counting from `triage_at`, falling back to `created_at`, and skipping a recent case with no `triage_at`.
  - The weekday regression test and the fallback test each fail on the pre-fix code.
- `python -m pytest tests/case` passes (25 tests) against the local PostgreSQL.

**Open items**

- `case_stable_reminder` still skips cases with no `stable_at` entirely rather than falling back to another timestamp. I left it alone because you asked only about the triage job.
- The catch-all branch for transitions into Triage should probably set `triage_at`. That would stop new null rows, but it doesn't backfill existing ones.
- Nothing is committed yet.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e
DEPLOYED_IMAGE: main-81d8ae42
FIRST_MISSED: 2025-08-18
MISSING_FIELD: triage_at