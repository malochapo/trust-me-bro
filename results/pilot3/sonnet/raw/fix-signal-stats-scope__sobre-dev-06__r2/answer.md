Fixed: `GET /{signal_id}/stats` now counts only the snooze filters attached to that signal. `GET /signals/stats` still counts them across all signals.

In `get_signal_stats` (`src/dispatch/signal/service.py`), when a `signal_id` is given, the snooze query now keeps only filters linked to that signal through `assoc_signal_filters`. Instance counts are untouched.

I added `test_get_signal_stats_snoozes_scoped_to_signal` in `tests/signal/test_signal_service.py`. It gives one signal one active snooze and another signal one active and one expired snooze, all on the same entity. The signal-scoped call returns 1 active and 0 expired. The unscoped call returns 2 active and 1 expired.

I ran `tests/signal/test_signal_service.py`: 15 passed, 1 skipped. I didn't run the rest of the suite.