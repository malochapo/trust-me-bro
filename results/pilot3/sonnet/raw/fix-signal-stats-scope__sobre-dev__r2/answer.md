The snooze counts from `GET /signals/{signal_id}/stats` now include only the filters attached to that signal. `GET /signals/stats` without a signal still counts every signal's snooze filters. All 7 tests in `tests/signal/test_signal_stats_service.py` pass. I did not run the rest of the suite.

The fix is in `get_signal_stats` in `src/dispatch/signal/service.py`. When `signal_id` is given, the snooze-count query is restricted to filters linked to that signal through `assoc_signal_filters`. I also added the missing import for that table.

The new test, `test_get_signal_stats_snooze_counts_scoped_to_signal`, creates two signals that each have snooze filters matching the same entity. It checks the active and expired counts for each signal alone and for the no-signal total.

I didn't change the existing snooze-count query so that it checks `action == snooze`. It still counts any filter whose expression matches the entity. That is outside this bug report.