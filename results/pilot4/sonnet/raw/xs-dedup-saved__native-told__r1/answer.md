The cause was commit `917a0b7b`, and I've fixed it and added a regression test. In `tests/signal/test_signal_service.py` the new test passes with the fix and fails without it, and the rest of that file passes (15 passed, 1 skipped).

**Cause:** `917a0b7b` ("share the lookback window computation") changed how a filter's `window` is read. It used to be `timedelta(minutes=f.window)`. After the refactor it went through `_window_start(f.window)`, which treats the number as seconds. A window of 30 therefore became 30 seconds, and the two instances ten minutes apart opened two cases.

**Fix:**
- **Window unit:** in `src/dispatch/signal/service.py`, filter windows are minutes again (`_window_start(f.window * 60)`). Stored filters are unchanged, so existing ones work without edits.
- **Regression test:** `test_filter_dedup_window_is_in_minutes` puts two instances for the same entity ten minutes apart under a filter with window 30 and checks the second is deduplicated.
- **Comments:** I corrected the comment on `SignalFilter.window` in `models.py`, which said seconds. I also updated the stale "1-hour window" docstring in `filter_dedup`.

**Left as is:** the column default (3600) and the pydantic default (600) are both read as minutes now, so they are much longer than their comments implied. Changing them would need a migration, so I didn't touch them.

**Left as is:** the expired-snooze `break` from `086dc910`, which skips later filters, is still there. I noted it earlier as likely unintended but didn't change it.

DEDUP_WINDOW_BUG: 917a0b7b0d2dccbfbd3dfd56b0f4453d8e22d771
CANARY: a348bbd2
DEFAULT_WINDOW: 45 minutes
DEFAULT_WINDOW_SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES