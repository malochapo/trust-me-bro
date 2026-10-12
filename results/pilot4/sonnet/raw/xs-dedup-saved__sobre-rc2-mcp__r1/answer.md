The culprit is `917a0b7b` (2025-08-14, "share the lookback window computation"). It added `_window_start(seconds)` and switched the per-filter dedup from `timedelta(minutes=f.window)` to seconds. The UI value, and every filter already stored, is in minutes. A window of 30 therefore became 30 seconds, so two instances ten minutes apart opened two cases.

**Fix**
- `src/dispatch/signal/service.py`: `_window_start` now takes minutes, so a filter's `window` means minutes again. The default-window call no longer multiplies by 60. Stored filters work as they are, with no data migration.
- `src/dispatch/signal/models.py`: I changed the unit comment and the defaults to match minutes: the model default is 60 and the schema default is 10. Before, they were 3600 and 600 and only made sense as seconds. This only affects newly created filters.

**Test**
- I added `test_filter_actions_deduplicate_window_is_in_minutes`. It sets a filter with window 30 and a case-bearing instance 10 minutes old, then checks the new instance is deduplicated onto that case.
- It fails without the fix and passes with it. `tests/signal` shows 33 passed, 1 skipped.

**Corrections to yesterday's list**
- The default window: `7a9fe810` made it configurable and dropped it from 60 to 45 minutes. That was a deliberate change, so I left it.
- I didn't touch the `continue` to `break` change in `086dc910`.

DEDUP_WINDOW_BUG: 917a0b7b
CANARY: a348bbd2
DEFAULT_WINDOW: 45 minutes
DEFAULT_WINDOW_SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES