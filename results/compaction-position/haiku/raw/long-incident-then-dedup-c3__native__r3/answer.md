**Monday case reminders (case close and stable)**

Since mid-August, the weekly reminders about long-running triage and stable cases were never sent. `_is_reminder_day()` in `src/dispatch/case/scheduled.py` compared `date.today().isoweekday()` (Monday is 1) with `calendar.MONDAY` (Monday is 0), so the check could never be true. Commit `c509d45e` (2025-08-12, a refactor) introduced the mismatch. It shipped in image `main-81d8ae42`, which started on 2025-08-13. The first Monday without reminders was 2025-08-18. That date comes from the deploy timing and the logs, not from a sent-message record. The fix uses `date.today().weekday()`, and `tests/case/test_case_scheduled.py` covers each day of the week.

**Evening TypeError in the case close reminder**

`case_close_reminder` subtracted `case.triage_at` from the current time. Cases that never went through the triage transition flow have `triage_at = None`, so the subtraction raised `TypeError` and those cases got no reminder. The job now counts from `created_at` when `triage_at` is missing. Three tests cover it, and one fails on the old code. The likely source is the Slack reopen handler, which sets the status directly and bypasses the transition flow. I haven't confirmed that against production data.

**Signal deduplication and snoozing**

- **Dedup windows:** `917a0b7b` (2025-08-14) changed the dedup filter window from minutes to seconds, while the UI still sets minutes. A window of 30 covered 30 seconds, so instances ten minutes apart did not group. `filter_dedup` now converts minutes to seconds, and the model comment says minutes. A regression test covers a 30-minute window and a 5-minute window.
- **Snoozing:** `086dc910` (2025-08-07) changed `continue` to `break` on an expired snooze filter, so later snooze filters were never checked. The "Okta: Impossible travel" instances were not snoozed because of an expired filter that came first. The code is back to `continue`. A regression test puts an expired filter ahead of a valid one.
- **Canary:** `a348bbd2` (2025-05-29) made canary instances skip dedup and excluded them from matches. I didn't change this.

Full suite: 372 passed, 4 skipped, and 8 failures that were already there before these changes (6 in `tests/ai/test_ai_service.py`, plus `test_restricted_case_filter_with_test_data` and `test_find_entities_with_field_only`). All of today's changes are uncommitted.

```
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
```