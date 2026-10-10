`GET /{organization}/signals/{signal_id}/stats` now counts only the snooze filters attached to that signal. `/signals/stats` without a signal still counts every filter.

- **Fix:** in `get_signal_stats` (`src/dispatch/signal/service.py`), when `signal_id` is given, the snooze-count query is restricted to filters linked to that signal through `assoc_signal_filters`. I also added the `assoc_signal_filters` import.
- **Test:** `test_get_signal_stats_snooze_counts_scoped_to_signal` in `tests/signal/test_signal_service.py`. It puts one active snooze filter on one signal and an active plus an expired one on another, all matching the same entity. It checks each signal's counts separately and then the unscoped totals.
- **Verification:** the signal tests pass (33 passed, 1 skipped). With the fix stashed, the new test fails.

I didn't change how the snooze counts treat filters whose action isn't snooze. They are still counted, as before, since the report was only about filters from other signals.