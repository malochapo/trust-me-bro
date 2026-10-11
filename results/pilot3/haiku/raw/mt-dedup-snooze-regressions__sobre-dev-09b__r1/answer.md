Recap of this session's changes (all uncommitted in the working tree):

- **Deduplication windows (`917a0b7b`)**: per-filter dedup windows were read as seconds instead of minutes, so a filter set to 30 in the UI covered 30 seconds. Fixed in `filter_dedup` to multiply by 60. Existing filters need no edits. Regression tests: `test_filter_actions_deduplicate_window_is_minutes` and `test_filter_actions_deduplicate_outside_window_minutes`.
- **Snoozing (`086dc910`)**: an expired snooze filter stopped the loop with `break`, so a valid snooze filter listed after it was never checked. Changed back to `continue`. Regression test: `test_filter_actions_snooze_expired_then_valid`.
- **Docs**: the `filter_signal` docstring and the `SignalFilter.window` column comment now describe the default and the window in the right units.
- **Test status**: `tests/signal` passes (35 passed, 1 skipped). The full suite has 8 failures in `tests/ai`, `tests/database`, and `tests/entity` that also fail on the original code.
- **Not changed**: the API default `SignalFilterBase.window = 600` and column default `3600` are still in the old numbers, which now mean 10 hours and 60 hours if omitted. `7a9fe810` also dropped the default dedup window from 60 to 45 minutes when it made the value configurable.

DEDUP_WINDOW_BUG: 917a0b7b
SNOOZE_BUG: 086dc910
CANARY: a348bbd2
DEFAULT_WINDOW: 45 minutes
DEFAULT_WINDOW_SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES