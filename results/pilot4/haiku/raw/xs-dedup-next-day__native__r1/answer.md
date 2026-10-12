The bug came from `917a0b7b` ("refactor(signal): share the lookback window computation", Aug 14 2025). Filter windows are stored and shown in minutes, but that commit started passing `f.window` to a helper that expects seconds. A 30-minute window became 30 seconds, so the two instances ten minutes apart were not grouped. The fix is in place and the signal suite passes (33 passed, 1 skipped).

I couldn't see yesterday's list in this session, so I rebuilt it from `git log` on `src/dispatch/signal/`. The relevant commits are `a348bbd2`, `4474af25`, `7a9fe810`, `086dc910`, `917a0b7b`, and `d2675cf4`.

**Fix**
- `src/dispatch/signal/service.py`: `_window_start` now takes minutes. Filter windows and the default window both pass minutes. Stored filters need no edits, and the UI and API are unchanged.
- `src/dispatch/signal/models.py`: the column comment now says minutes. I did not change the column default (`60 * 60`) or the API schema default (`600`). Read as minutes, those mean 60 hours and 10 hours, so they may be worth a separate look.
- `docs/docs/administration/settings/signal/filter.mdx` and the `filter_signal` docstring: the default is described as 45 minutes and tied to the setting, instead of "one hour".
- Regression test `test_filter_actions_deduplicate_window_is_minutes` in `tests/signal/test_signal_service.py`: window 30, instances ten minutes apart, expects deduplication. It fails without the fix and passes with it.

**Not fixed: a second regression in `086dc910`**
In `filter_snooze`, the expired-snooze check changed from `continue` to `break`. An expired snooze filter now stops evaluation of any later active snooze filters. This is a snooze bug, not a dedup-window one, so I left it alone. It is a one-word change if you want it.

DEDUP_WINDOW_BUG: 917a0b7b
CANARY: a348bbd2
DEFAULT_WINDOW: 45 minutes
DEFAULT_WINDOW_SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES