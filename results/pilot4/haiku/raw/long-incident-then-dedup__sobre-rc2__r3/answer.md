**Recap for the weekly report**

**Investigation 1: missing Monday reminders.** Assignees stopped getting the weekly Monday close reminders for long-running triage and stable cases. The daily triage reminders kept arriving. The cause was commit `c509d45e` (2025-08-12, "share the weekly reminder check"). It changed `_is_reminder_day()` to compare `date.today().isoweekday()` (Monday = 1) with `calendar.MONDAY` (Monday = 0), so the check was always false. The fix uses `weekday()`, and tests cover all seven weekdays and both reminder jobs. The bad commit reached production in image `main-81d8ae42`, deployed 2025-08-13 16:40 UTC. The previous image, `main-b05613b5`, predates the commit. The first Monday that was missed is 2025-08-18.

**Investigation 2: the close reminder TypeError.** The `case-close-reminder` job logged a TypeError every evening. The job ran `datetime.utcnow() - case.triage_at`, and some triage cases have `triage_at` set to NULL. Only `case_triage_status_flow` sets that field, and some paths put a case into triage without running it. The fix counts from `created_at` when `triage_at` is missing. Two tests cover the fallback and the precedence of `triage_at`. I did not confirm which code path created the affected cases.

**Investigation 3: the window and snooze reports.**
- **Deduplication windows.** Commit `917a0b7b` (2025-08-14) changed the per-filter window from minutes to seconds. A filter set to 30 in the UI looked back 30 seconds, so instances ten minutes apart were not grouped. The fix restores minutes. Existing filters keep their stored values and behave as they did before the change, and a regression test covers the 10- and 40-minute cases.
- **Snoozing.** Commit `086dc910` (2025-08-07) changed the expired-snooze branch from `continue` to `break`. An expired filter earlier in the list ended the loop, so a valid filter after it was never checked. The fix restores `continue`, with a regression test.
- **Canary signals.** Commit `a348bbd2` (2025-05-29) made canary signals skip deduplication and excluded them from the dedup query.
- **Default grouping window.** Signals with no filters use a 45-minute window, set by `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`. Commit `7a9fe810` (2025-06-19) made this configurable and shortened the default from one hour to 45 minutes.

**Test results:** `python -m pytest tests/signal tests/case` gives 62 passed and 1 skipped. The rest of the suite, excluding `tests/ai`, gives 363 passed, 4 skipped, and 2 failures. Both failures also occur with my changes stashed. `tests/ai` needs network access to download a tokenizer and fails with or without my changes.

**Open items, not changed:**
- The default filter values still assume seconds (`SignalFilter.window` defaults to 3600 and the API default is 600), which would now be read as minutes.
- A filter created through the API with a seconds value would now behave as minutes.
- Case-stable reminders skip cases with no `stable_at` instead of falling back to another date.

Nothing is committed.

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