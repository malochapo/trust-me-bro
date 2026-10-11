**Recap**

- **Symptom:** since mid-August, assignees stopped getting the Monday reminders for long-running triage and stable cases. The daily triage reminders kept arriving because that job has no Monday check.
- **Root cause:** commit `c509d45e` ("refactor(case): share the weekly reminder check", 2025-08-12) added `_is_reminder_day()`, which compared `date.today().isoweekday()` to `calendar.MONDAY`. `isoweekday()` numbers Monday as 1, while `calendar.MONDAY` is 0, so the check never matched and both weekly jobs went silent.
- **Deploy:** image `main-81d8ae42` started on the scheduler and web pods on 2025-08-13 at about 16:40Z. The previous image, `main-b05613b5`, does not contain the commit.
- **Evidence:** the Monday 18:00 runs sent 5, 7 and 6 case close reminders on 07-28, 08-04 and 08-11. On 08-18, the first Monday after the deploy, they sent none.
- **Fix (uncommitted):** `_is_reminder_day()` now uses `weekday()`, which also numbers Monday as 0. A regression test runs the real jobs on a faked Monday and Tuesday.
- **Second issue:** `case_close_reminder` logged a `datetime - None` TypeError every evening. `triage_at` is only set by the triage transition flow, so triage cases that never went through it have none, and the error stopped those cases getting reminders. The job now falls back to `created_at`, with a test. I haven't confirmed in the database why those cases lack `triage_at`.
- **Not covered:** reminders missed since 08-18 won't be sent retroactively. `case_stable_reminder` still skips stable cases that have no `stable_at`, with no fallback. I ran only the new test file, not the whole suite, and nothing is committed.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e
DEPLOYED_IMAGE: main-81d8ae42
FIRST_MISSED: 2025-08-18
MISSING_FIELD: triage_at