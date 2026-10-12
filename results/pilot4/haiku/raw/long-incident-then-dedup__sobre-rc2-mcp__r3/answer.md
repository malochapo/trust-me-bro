**Weekly reminders (Monday case close and stable reminders)**

Monday reminders stopped after commit `c509d45e` (2025-08-12, "refactor(case): share the weekly reminder check"). That commit changed `_is_reminder_day()` in `src/dispatch/case/scheduled.py` to compare `date.today().isoweekday()` with `calendar.MONDAY`. `calendar.MONDAY` is 0, and `isoweekday()` returns 1 for Monday, so the check never matched. I changed it to `date.today().weekday() == calendar.MONDAY`. Regression tests are in `tests/case/test_case_scheduled.py`, covering each weekday, the close and stable reminders, and the new fallback. I checked that the weekday tests fail with the bug reintroduced.

The deploy that shipped it is not confirmed. The repo tags stop in 2024, and the logs carry no image tag. The scheduler restarted at 2025-08-13 16:40 UTC, which is the likely deploy, but that is not proven.

**Evening TypeError**

The close reminder subtracted `case.triage_at` from the current time. Some cases in triage have `triage_at` NULL, so each evening's run raised a `TypeError` for those cases. The likely source is migration `391f7c3e6992` (2022-08-01), which added `triage_at` with no backfill. The fix uses `triage_at or created_at`. This is not yet confirmed in production. The check is `SELECT count(*) FROM "case" WHERE status = 'triage' AND triage_at IS NULL;`. Also, `reopen_button_click` in the Slack plugin sets `status = triage` without running the flow that sets `triage_at`, so new NULLs can still appear.

**Signal deduplication and snoozing**

- Windows: commit `917a0b7b` (2025-08-14) read the stored filter `window` as seconds. The UI labels it "Window (minutes)", so a 30-minute window became 30 seconds. The fix converts minutes to seconds (`f.window * 60`) in `src/dispatch/signal/service.py`. The column default changed from 60 × 60 to 60, and its comment now says minutes. The regression test is `test_filter_dedup_window_is_minutes`. The signal suite passes: 34 passed at that point, 1 skipped.
- Snoozing: commit `086dc910` (2025-08-07) changed `continue` to `break` on an expired snooze filter, so a later active filter on the same signal was never checked. The fix restores `continue`. The regression test is `test_filter_actions_snooze_after_expired_filter`. The signal suite passes: 35 passed, 1 skipped.
- Canary signals: `a348bbd2` (2025-05-29) made canary signals skip deduplication, which is intended. It is not a bug.

Still open: the 8 test failures in the full suite predate today's work (`tests/ai/test_ai_service.py` ×6, `tests/database/test_service.py`, `tests/entity/test_entity_service.py`). The `SignalFilterBase` schema default `window = 600` is now 10 hours, and I left it unchanged. Nothing is committed.

```
FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e
DEPLOYED_IMAGE: unknown (not recorded in repo or logs; scheduler restart 2025-08-13 16:40 UTC is the likely deploy)
FIRST_MISSED: 2025-08-18
MISSING_FIELD: triage_at
DEDUP_WINDOW_BUG: 917a0b7b
SNOOZE_BUG: 086dc910
CANARY: a348bbd2
DEFAULT_WINDOW: 45 minutes
DEFAULT_WINDOW_SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES
```