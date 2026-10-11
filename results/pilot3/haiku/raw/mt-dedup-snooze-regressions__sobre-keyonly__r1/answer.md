Recap of this session's changes (all uncommitted in the working tree):

- **Deduplication windows:** Commit `917a0b7b` read per-filter `window` values as seconds instead of minutes, so a 30-minute window became 30 seconds. Fixed in `src/dispatch/signal/service.py` by reading the window as minutes again. Model defaults in `src/dispatch/signal/models.py` are now 60 and 10 minutes. Regression test: `test_filter_actions_deduplicate_window_is_minutes`.
- **Snoozing:** Commit `086dc910` changed an expired snooze filter from `continue` to `break`, which stopped evaluation before later valid filters. Fixed by restoring `continue`. Regression test: `test_filter_actions_snooze_expired_before_active`.
- **Canary signals:** Commit `a348bbd2` stopped canary signals from being deduplicated. No change here.
- **Default grouping window:** Commit `7a9fe810` made the default window configurable. Its default is now 45 minutes, down from the earlier hard-coded 1 hour.

Tests: `python -m pytest tests/signal` passes (34 passed, 1 skipped). The full suite has 8 failures in the AI, database, and entity tests that also fail on unmodified `HEAD`.

```
DEDUP_WINDOW_BUG: 917a0b7b
SNOOZE_BUG: 086dc910
CANARY: a348bbd2
DEFAULT_WINDOW: 45 minutes
DEFAULT_WINDOW_SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES
```