The cause is commit `917a0b7b` ("refactor(signal): share the lookback window computation", 2025-08-14). The UI offers 5–30 and stores that number as-is, and the code treated it as minutes until that commit. The commit switched the filter path to `timedelta(seconds=f.window)`, so a window of 30 became 30 seconds. Two instances ten minutes apart therefore never matched.

I don't have yesterday's list in this conversation, so I rebuilt it from `git log --since=2025-05-22` on the signal code. The dedup and snooze changes are `a348bbd2`, `7a9fe810`, `4474af25`, `086dc910` and `917a0b7b`. Only `917a0b7b` changed how a filter's window is computed.

**Fix**
- `src/dispatch/signal/service.py`: the filter path now converts minutes to seconds (`_window_start(f.window * 60)`). Existing filters need no edits, since their stored values are already minutes. The default-window path was never broken.
- `src/dispatch/signal/models.py`: the column comment now says minutes. I also changed the Python-side default from 3600 to 60, since 3600 would have meant 60 hours under the minutes convention. No migration is needed because it is not a server default.
- `filter_signal`'s docstring said the default window was 1 hour; it now points at the setting.

**Regression tests** (`tests/signal/test_signal_service.py`)
- `test_filter_window_is_in_minutes`: window 30, instance from 10 minutes ago, expects deduplication. It failed before the fix and passes now.
- `test_filter_window_short_does_not_match_older_instance`: window 5, same instance, expects no match. This guards the unit from the other side.

`python -m pytest tests/signal` gives 34 passed, 1 skipped. I did not run the full suite.

**Found but not fixed:** `086dc910` changed `continue` to `break` in `filter_snooze` for expired snooze filters. An expired snooze now stops evaluation of every later snooze filter on the signal, so a later active snooze can be missed. The fix is a one-word change back to `continue`. I left it alone because you asked about dedup windows; say the word and I'll make it.

DEDUP_WINDOW_BUG: 917a0b7b
CANARY: a348bbd2
DEFAULT_WINDOW: 45 minutes
DEFAULT_WINDOW_SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES