Here's the recap for both investigations. The fixes are uncommitted in the working tree.

**Investigation 1: missing Monday case reminders**
- Long-running triage and stable cases stopped getting their weekly reminders. The daily triage reminders kept arriving.
- Cause: `_is_reminder_day()` in `src/dispatch/case/scheduled.py` compared `date.today().isoweekday()` (Monday = 1) with `calendar.MONDAY` (Monday = 0), so it was never true. Commit `c509d45e` (2025-08-12, "refactor(case): share the weekly reminder check") introduced this when it moved the check into the helper. Before that, the code compared `isoweekday()` with `1`, which was correct.
- Shipped in image `main-81d8ae42`, which started on the scheduler at 2025-08-13 16:40 and contains `c509d45e`.
- Last Monday with case reminders in the logs was 2025-08-11. The first missed Monday was 2025-08-18, when only the incident close reminder was logged.
- Fix: `weekday() == calendar.MONDAY`. Regression tests in `tests/case/test_case_scheduled.py` fail on the old code.

**Investigation 2: evening TypeError in the case close reminder**
- Cause: some triage cases have no `triage_at`, so `datetime.utcnow() - case.triage_at` raised `TypeError`. The error was caught per case, so the job continued but those cases got no reminder. It first appeared 2025-08-16.
- Source of the NULL values is not confirmed: `triage_at` is only set by `case_triage_status_flow`, and the logs don't name the affected cases.
- Fix: `span = datetime.utcnow() - (case.triage_at or case.created_at)`. Two tests were added.
- Not changed: `case_stable_reminder` still skips stable cases with no `stable_at`.

**Signal bugs (also from this batch of commits)**
- Deduplication windows: commit `917a0b7b` changed the per-filter window from minutes to seconds, so a window of 30 became 30 seconds. Fixed in `src/dispatch/signal/service.py`, with a regression test.
- Snoozing: commit `086dc910` changed an expired snooze from `continue` to `break`, which stopped checking later snooze filters. Fixed, with a regression test.
- Canary signals: commit `a348bbd2` made canary instances skip deduplication.

**Open items:** the `SignalFilterBase.window` default of 600 and the `SignalFilter.window` column default of 3600 were written for seconds. They are now read as minutes, so those defaults are much longer than intended. I left them unchanged.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e
DEPLOYED_IMAGE: main-81d8ae42
FIRST_MISSED: 2025-08-18
MISSING_FIELD: triage_at
DEDUP_WINDOW_BUG: 917a0b7b
SNOOZE_BUG: 086dc910
CANARY: a348bbd2
DEFAULT_WINDOW: 45 minutes
DEFAULT_WINDOW_SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES