Recap of this session's changes to snooze and dedup decisions, plus the uncommitted fixes:

- **Dedup window in minutes (fixed):** commit `917a0b7b` read custom dedup filter windows as seconds, although the UI sets them in minutes. Windows are now converted from minutes in `filter_dedup`. Regression test: `test_filter_window_is_in_minutes`.
- **Expired snooze stopped evaluation (fixed):** commit `086dc910` changed an expired snooze filter from `continue` to `break`, so later valid snooze filters were skipped. The check now uses `continue`. Regression test: `test_filter_actions_snooze_after_expired_snooze`.
- **Canary signals (unchanged this session):** commit `a348bbd2` excludes canary signals from deduplication, both as candidates and as matches.
- **Default grouping for filterless signals:** 45 minutes, set by `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` (commit `7a9fe810`).

The fixes are uncommitted in the working tree. Signal tests pass: 34 passed, 1 skipped.

DEDUP_WINDOW_BUG: 917a0b7b
SNOOZE_BUG: 086dc910
CANARY: a348bbd2
DEFAULT_WINDOW: 45 minutes
DEFAULT_WINDOW_SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES