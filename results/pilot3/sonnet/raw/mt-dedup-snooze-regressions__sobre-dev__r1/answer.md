**Recap**

- **Dedup windows:** commit `917a0b7b` (2025-08-14) was billed as a refactor but changed a filter's `window` from minutes to seconds. A window of 30 in the UI became 30 seconds. I fixed it in `signal/service.py` by multiplying the window by 60, and added `test_filter_actions_deduplicate_window_is_in_minutes`.
- **Snoozing:** commit `086dc910` (2025-08-07) changed `continue` to `break` on an expired snooze filter. An expired filter listed first stopped a later valid one from applying. I restored `continue` and added `test_filter_actions_snooze_skips_expired_filter`.
- **Canary signals:** commit `a348bbd2` (2025-05-29) made canary instances skip deduplication and excluded canaries from the dedup lookups.
- **Default window:** signals with no filters group over 45 minutes. Commit `7a9fe810` made this configurable, replacing a hard-coded 1 hour.
- **State:** the changes are uncommitted in the working tree. `tests/signal/test_signal_service.py` passes, with 16 passed and 1 skipped.
- **Left alone:** the `window` column default (`60 * 60`) and the schema default (600) in `signal/models.py` still describe seconds. The `filter_signal` docstring still says "1-hour" for the default window.

DEDUP_WINDOW_BUG: 917a0b7b
SNOOZE_BUG: 086dc910
CANARY: a348bbd2
DEFAULT_WINDOW: 45 minutes
DEFAULT_WINDOW_SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES