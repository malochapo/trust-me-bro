Here's the recap. None of the fixes is committed yet. The working tree has the changes in `src/dispatch/signal/service.py`, `src/dispatch/signal/models.py`, and `tests/signal/test_signal_service.py`.

- **Dedup windows:** `917a0b7b` started reading `SignalFilter.window` as seconds, although the UI sends minutes. A 30-minute window became 30 seconds. The fix reads it as minutes again, with a regression test in `test_filter_window_is_in_minutes`.
- **Snoozing:** `086dc910` changed an expired snooze filter from `continue` to `break`, so a valid snooze filter after an expired one was never checked. The fix restores `continue`, with a regression test in `test_filter_actions_snooze_after_expired_snooze`.
- **Canary signals:** `a348bbd2` stopped canary instances from being deduplicated and from counting as dedup candidates. It is the intended behaviour, so I didn't change it.
- **Default window:** signals with no filter are grouped over 45 minutes. The value is set by `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`, which can be overridden through the environment.

Tests: `tests/signal` passes (35 passed, 1 skipped). The full suite has 8 failures that predate these changes, in `tests/ai/test_ai_service.py` and two other tests.

DEDUP_WINDOW_BUG: 917a0b7b
SNOOZE_BUG: 086dc910
CANARY: a348bbd2
DEFAULT_WINDOW: 45 minutes
DEFAULT_WINDOW_SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES