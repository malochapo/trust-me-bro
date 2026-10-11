`GET /signals/{signal_id}/stats` now counts only the snooze filters attached to that signal. `GET /signals/stats` still counts the filters of every signal. The stats tests pass (7 passed).

The fix is in `get_signal_stats` in `src/dispatch/signal/service.py`. When `signal_id` is given, the snooze-filter query is limited to filters linked to that signal through `assoc_signal_filters`. The instance counts are untouched.

I added `test_get_signal_stats_scoped_to_signal` in `tests/signal/test_signal_stats_service.py`. It gives two signals one snooze filter each, with the same entity and one active and one expired. It checks signal 1 gives (1 active, 0 expired), signal 2 gives (0, 1), and no signal gives (1, 1). I only ran that test file, not the full suite.