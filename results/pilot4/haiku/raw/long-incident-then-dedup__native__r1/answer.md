## Recap

**Weekly reminders (investigation 1 and fix).** Assignees stopped getting the Monday close and stable reminders after the deploy on 2025-08-13. The cause was `_is_reminder_day` in `src/dispatch/case/scheduled.py`. It compared `date.today().isoweekday()` (Monday is 1) with `calendar.MONDAY` (Monday is 0), so the check never matched. Commit `c509d45e` (2025-08-12, "share the weekly reminder check") introduced it, and it shipped in `main-81d8ae42`. The fix uses `weekday()`. A regression test in `tests/case/test_case_scheduled.py` fails on the old code and passes on the new.

**Evening TypeError (investigation 3).** The close reminder subtracted `case.triage_at` from the current time, and `triage_at` is NULL on some triaging cases. The job now counts from `triage_at or created_at`, and a test covers a case with no `triage_at`. I didn't confirm which production path leaves `triage_at` empty. The likely candidates are the transitions that skip `case_triage_status_flow` and the Slack reopen button, which sets the status directly. Stable reminders still skip cases with no `stable_at`, and I left that as it was.

**Deduplication windows (investigation 2).** Commit `917a0b7b` (2025-08-14) changed per-filter dedup windows from minutes to seconds. A window of 30 looked back 30 seconds, so instances ten minutes apart opened separate cases. The fix restores minutes and changes the `SignalFilter.window` column default to 60 (one hour). The regression test `test_filter_window_is_in_minutes` fails on the seconds behaviour and passes now.

**Snoozing (investigation 2, second report).** Commit `086dc910` (2025-08-07) changed the expired-snooze branch in `filter_snooze` from `continue` to `break`. An expired filter earlier in the list stopped the loop, so a valid snooze filter after it was never checked. The fix restores `continue`, and `test_filter_actions_snooze_after_expired_filter` covers it.

**Canary signals.** Commit `a348bbd2` (2025-05-29, #6026) made canary signals skip deduplication and excluded them from dedup candidates. That behaviour is still in place, and I didn't change it.

**Default grouping window.** Signals with no filter group over 45 minutes. Commit `7a9fe810` made that value configurable, and before it the value was a hard-coded 1 hour.

Status: all of the above is in the working tree and uncommitted. `python -m pytest tests/signal tests/case` gives 57 passed, 1 skipped.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e
DEPLOYED_IMAGE: registry.example.com/dispatch:main-81d8ae42
FIRST_MISSED: 2025-08-18
MISSING_FIELD: triage_at
DEDUP_WINDOW_BUG: 917a0b7b
SNOOZE_BUG: 086dc910
CANARY: a348bbd2
DEFAULT_WINDOW: 45 minutes
DEFAULT_WINDOW_SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES