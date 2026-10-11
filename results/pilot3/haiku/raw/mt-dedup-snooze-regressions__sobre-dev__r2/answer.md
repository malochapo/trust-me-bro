Recap of this session's work on the Dispatch signal filters:

- **Dedup window units (fixed, uncommitted):** Commit `917a0b7b` changed expression-filter dedup windows from minutes to seconds, so a 30-minute window looked back 30 seconds. The fix in `src/dispatch/signal/service.py` reads the stored value as minutes again, so existing filters work unchanged. A regression test covers it.
- **Snooze after an expired filter (fixed, uncommitted):** Commit `086dc910` changed an expired snooze filter from `continue` to `break`, which stopped the loop before later valid filters were checked. The fix restores `continue`. A regression test covers it.
- **Canary signals:** Commit `a348bbd2` made dedup skip canary signals, both as the incoming instance and as match candidates.
- **Default grouping:** Signals with no filters are grouped by a 45-minute default window, set by `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`.

Open items, not changed: the column default for `SignalFilter.window` is 60 hours, and the API schema default is 10 hours. The `filter_signal` docstring still says 1 hour.

DEDUP_WINDOW_BUG: 917a0b7b
SNOOZE_BUG: 086dc910
CANARY: a348bbd2
DEFAULT_WINDOW: 45 minutes
DEFAULT_WINDOW_SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES