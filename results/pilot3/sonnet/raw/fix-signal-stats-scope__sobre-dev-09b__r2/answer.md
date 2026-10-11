Fixed: with a `signal_id`, `get_signal_stats` now counts only the snooze filters attached to that signal. Without one it still counts every signal's filters. The signal stats tests pass (7 passed), including the new one.

- **Fix:** in `src/dispatch/signal/service.py`, the snooze-count query now adds a condition when `signal_id` is given. It keeps only filters whose id appears in `assoc_signal_filters` for that signal. I also imported `assoc_signal_filters` from `.models`.
- **Test:** I added `test_get_signal_stats_snoozes_scoped_to_signal` to `tests/signal/test_signal_stats_service.py`. It creates two signals matching the same entity, one with one active filter and the other with one active and one expired. It checks that each signal reports its own counts and that no `signal_id` gives the combined 2 active and 1 expired.

I only ran the stats test file, not the full suite.