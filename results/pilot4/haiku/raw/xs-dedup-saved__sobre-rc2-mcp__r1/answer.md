The window bug came from `917a0b7b`, which switched custom dedup windows from minutes to seconds. The UI still sends minutes, so a 30 meant 30 seconds, and two instances ten minutes apart never grouped. I fixed it, added a regression test, and the signal suite passes (33 passed, 1 skipped). I haven't committed.

I didn't have yesterday's conversation, so I re-derived the commit list from the repo and the memory note. Checking the diffs, the list was accurate.

**Changes**
- `src/dispatch/signal/service.py`: `_window_start` takes minutes again. The custom-filter path passes `f.window` unchanged, and the default path passes `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` directly. I also corrected the `filter_signal` docstring, which said the default was 1 hour.
- `src/dispatch/signal/models.py`: the column default is now 60 and the API schema default is now 10, both in minutes. The old values, 3600 and 600, were seconds. These only apply to new filters that don't send a window. Existing rows are untouched, so no edits or migration are needed.
- `tests/signal/test_signal_service.py`: `test_filter_actions_deduplicate_window_is_minutes` puts an earlier instance 10 minutes old under a `window=30` filter and expects the second instance to be deduplicated. It failed before the fix and passes after.

**Not fixed:** `086dc910` also changed `filter_snooze`. An expired snooze filter now `break`s the loop instead of `continue`, so later active snooze filters are skipped. That is a snooze bug, not a window bug, so I left it alone. It needs a separate decision.

**Open question:** I couldn't tell whether any API callers started sending seconds after `917a0b7b`. Those filters would now be 60× longer than intended. Worth checking the stored windows.

DEDUP_WINDOW_BUG: 917a0b7b
CANARY: a348bbd2
DEFAULT_WINDOW: 45 minutes
DEFAULT_WINDOW_SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES