Recap of this session's changes, all uncommitted in the working tree:

- **Deduplication windows:** `917a0b7b` made per-filter dedup windows read minutes as seconds. Filters created in the UI were effectively 60 times shorter. The fix reads the window as minutes again, which matches the UI. Existing filters need no edits. The column comment now says minutes. A regression test covers a 30-minute window with instances 10 minutes apart.
- **Snoozing:** `086dc910` changed an expired snooze filter from `continue` to `break`, so a valid snooze filter listed after an expired one was never checked. The fix restores `continue`. A regression test covers an expired filter listed before a valid one.
- **Canary signals:** `a348bbd2` skips deduplication for canary signals. This was intended, and I did not change it.
- **Docs:** the `filter_signal` docstring now gives the configured default window instead of "1 hour".
- **Tests:** `python -m pytest tests/signal` gives 35 passed, 1 skipped.

Open items: the `SignalFilter.window` defaults (3600 in the column, 600 in the schema) now read as 60 hours and 10 hours. I did not change them.

DEDUP_WINDOW_BUG: 917a0b7b
SNOOZE_BUG: 086dc910
CANARY: a348bbd2
DEFAULT_WINDOW: 45 minutes
DEFAULT_WINDOW_SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES