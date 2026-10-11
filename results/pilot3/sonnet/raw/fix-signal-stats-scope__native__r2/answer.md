I fixed the bug. `GET /signals/{signal_id}/stats` now counts only the snooze filters attached to that signal. The new test and the existing signal stats tests pass (7 in `tests/signal/test_signal_stats_service.py`). I didn't run the rest of the suite.

The change is in `get_signal_stats` in `src/dispatch/signal/service.py`. When a `signal_id` is given, the snooze count query is limited to filters linked to that signal through `assoc_signal_filters`. Without a `signal_id`, as in `GET /signals/stats`, it still counts the snooze filters of every signal. I didn't touch the instance counts.

The new test is `test_get_signal_stats_snoozes_scoped_to_signal` in `tests/signal/test_signal_stats_service.py`. It sets up two signals that share an entity:
- **Signal 1:** one active snooze filter.
- **Signal 2:** one active and one expired snooze filter.

It checks that signal 1 gives 1 active and 0 expired, signal 2 gives 1 active and 1 expired, and no signal gives 2 active and 1 expired.