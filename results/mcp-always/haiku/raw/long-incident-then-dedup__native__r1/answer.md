Here is the recap for both investigations. The changes are in the working tree and nothing is committed.

**Monday reminders and the evening TypeError**
- Weekly Monday reminders stopped after the 2025-08-13 deploy. `_is_reminder_day()` in `src/dispatch/case/scheduled.py` compared `date.today().isoweekday()` (Monday = 1) with `calendar.MONDAY` (Monday = 0). The check was never true, so no Monday reminders went out. The bad line came in with `c509d45e` (2025-08-12, "share the weekly reminder check"). The fix changes it to `date.today().weekday()`. The logs show close reminders on 2025-08-11 and none on 2025-08-18.
- The deploy was image `main-81d8ae42`. It started on the web and scheduler pods on 2025-08-13.
- The evening TypeError comes from `case_close_reminder`. `case.triage_at` is `None` for some triage cases, and subtracting it from `datetime.utcnow()` raised the error. The fix counts from `created_at` when `triage_at` is missing. Three tests cover it. The root cause is not confirmed: the likely source is the Slack reopen handler (`reopen_button_click`), which sets status to triage without setting `triage_at`. The logs don't name the case, so the source has not been verified. That handler is unchanged.
- Tests: `python -m pytest tests/case` passes, 25 tests.

**Snooze and deduplication**
- A deduplication window that was entered in minutes in the UI was treated as seconds after `917a0b7b` (2025-08-14). A 30-minute window became 30 seconds, so two instances ten minutes apart opened two cases. The fix reads windows in minutes again, so existing filters work without edits. Two regression tests cover it.
- The snooze bug came from `086dc910` (2025-08-07). An expired snooze filter now stopped the loop with `break`, so valid filters later in the list were never checked. The fix changes it back to `continue`. One regression test covers it.
- The canary behaviour changed in `a348bbd2` (2025-05-29): canary instances skip deduplication and are excluded from matching. No tests were added for that change in this session.
- Tests: `python -m pytest tests/signal` passes, 35 tests, 1 skipped. The full suite was not run.
- The default grouping window for signals with no filter is 45 minutes. It is set by `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`.

**Open items**
- Per-filter default windows: the model default is 3600 and the schema default is 600, now read as minutes. That is 60 hours and 10 hours. Decide whether these should be 60 and 10.
- `917a0b7b` is on `main` but not in deployed `81d8ae42`. `086dc910` is in the deployed image, so the snooze bug is live.
- The missing-`triage_at` source is unconfirmed, and the reopen path is still open.
- Nothing is committed.

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