Changes made in this session, none committed yet:

- **Dedup windows:** custom filter windows were read as seconds instead of minutes, so a window of 30 grouped only 30 seconds of instances. `_window_start` now takes minutes, and the model's column default is 60 and schema default is 10. Existing filters work unchanged, since the UI has always stored minutes. Regression test: `test_filter_actions_deduplicate_window_is_minutes`.
- **Snoozing:** an expired snooze filter stopped the loop, so a valid snooze listed after it was never applied. Expired filters are now skipped with `continue`. Regression test: `test_filter_actions_snooze_expired_filter_does_not_hide_active_snooze`.
- **Verification:** `python -m pytest tests/signal` gives 34 passed and 1 skipped.
- **Stale docs:** the `filter_signal` docstring and the model comment now describe the minute units and the 45-minute default.

Note for the changelog: filters created through the API with a seconds value on purpose will now be 60 times longer. The UI never produces those.

DEDUP_WINDOW_BUG: 917a0b7b
SNOOZE_BUG: 086dc910
CANARY: a348bbd2
DEFAULT_WINDOW: 45 minutes
DEFAULT_WINDOW_SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES