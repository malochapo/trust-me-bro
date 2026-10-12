**Weekly reminders and the evening TypeError (both in `src/dispatch/case/`)**

- **Missed Monday reminders:** `_is_reminder_day()` compared `date.today().isoweekday()` (Monday = 1) with `calendar.MONDAY` (Monday = 0). The check was never true, so no weekly close or stable reminder went out on any day. Commit `c509d45e` (2025-08-12) introduced it. The image containing it is `main-81d8ae42` (started 2025-08-13 16:40Z), which includes `c509d45e`. The fix uses `date.today().weekday() == calendar.MONDAY`. The regression test covers Monday and Tuesday through Sunday.
- **Evening TypeError:** `case_close_reminder` computed `datetime.utcnow() - case.triage_at`. Slack handlers in `plugins/dispatch_slack/case/interactive.py` set a case to triage by assigning `case.status` directly, which skips `case_triage_status_flow`, so `triage_at` stays NULL. The job now counts from `triage_at or created_at`. The regression test sets an 8-day-old case with no `triage_at` and expects a reminder, and a 2-day-old case in the same project and expects none.
- **Log caveat:** The TypeError appears in `scheduler.log` from 2025-07-28, before the 08-13 image started. The logs don't tie it to that deploy, and the cause is the missing field regardless.

**Signal bugs**

- **Dedup windows ignored the UI's minutes:** Commit `917a0b7b` (2025-08-14) treated `SignalFilter.window` as seconds, so a 30-minute window became 30 seconds. The fix reads it as minutes again and corrects the column comment. The regression test is `test_filter_dedup_window_is_in_minutes`.
- **Snoozes broken by an expired filter:** Commit `086dc910` (2025-08-07) changed an expired snooze filter from `continue` to `break`, so a valid snooze filter later in the list was never checked. The fix restores `continue`. The regression test is `test_filter_actions_snooze_expired_filter_before_valid_filter`.
- **Canary signals:** Commit `a348bbd2` (2025-05-29) makes canary instances skip dedup and excludes them from matches.
- **Default window:** Signals with no filters group instances within 45 minutes, set by `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` (commit `7a9fe810`, 2025-06-19; it was 1 hour before).

**State**

- Full suite: 370 passed, 4 skipped, 8 failed. The 8 failures predate today's work (`tests/ai/test_ai_service.py`, `tests/database/test_service.py::test_restricted_case_filter_with_test_data`, `tests/entity/test_entity_service.py::test_find_entities_with_field_only`).
- `python -m pytest` still fails on `slack_sdk`, so I ran tests with the `pytest.main` workaround.
- Nothing is committed. Open choice: the column default for a filter created without a window is 3600 minutes (about 2.5 days). I left it unchanged.

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