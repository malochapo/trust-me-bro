**Recap**

**1. Missing Monday reminders**
- **Cause:** the helper `_is_reminder_day()` in `src/dispatch/case/scheduled.py` compared `date.isoweekday()` (Monday = 1) with `calendar.MONDAY` (0). That is never true, so the weekly close reminders for triage and stable cases stopped. The daily reminders use different code and kept working.
- **Introduced by:** commit `c509d45e`.
- **Deployed in:** image `main-81d8ae42`, rolled out around 2025-08-13 16:40Z. The previous image was `main-b05613b5`.
- **First missed Monday:** 2025-08-18.
- **Fix:** it now uses `weekday()`. The regression test is `test_is_reminder_day` in `tests/case/test_case_scheduled.py`, parametrized over Monday to Sunday. It fails against the old code.

**2. Evening TypeError in the case close reminder job**
- **Cause:** `case_close_reminder` computed `datetime.utcnow() - case.triage_at`. `triage_at` is only set when a case transitions into triage, so cases created directly in triage have none. The subtraction raised a TypeError, which the job caught and logged, and those cases never got a reminder.
- **Fix:** the job now counts from `case.triage_at or case.created_at`. The new test covers cases with and without `triage_at`, both old and recent.
- **Not changed:** `case_stable_reminder` still skips cases with no `stable_at`.

**3. Signal dedup and snooze**
- **Dedup windows (`917a0b7b`, 2025-08-14):** this labelled-refactor commit made per-filter windows apply as seconds, but the UI and stored data use minutes. A window of 30 became 30 seconds. `_window_start` now takes minutes, and existing filters work without editing.
- **Snooze (`086dc910`, 2025-08-07):** an expired snooze filter now ended the loop (`break`) and hid later valid filters. It is `continue` again.
- **Tests:** there is a regression test for each fix, and both fail against the old code.
- **Canary signals:** `a348bbd2` (2025-05-29) excludes canary signals from deduplication, in both directions.
- **Default window:** signals with no filter group instances within 45 minutes by default. `7a9fe810` made this configurable. Before that it was a hardcoded 1 hour.

**Still open**
- **Column defaults:** the `SignalFilter.window` column default is `60 * 60` and the schema default is 600. Read as minutes, those are 60 and 10 hours, and I left them alone.
- **Lint:** ruff isn't installed here, so lint and format weren't checked.
- **Commits:** nothing is committed.

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