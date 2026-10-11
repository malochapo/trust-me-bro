`GET /signals/{signal_id}/stats` now counts only the snooze filters attached to that signal. `GET /signals/stats` without a signal still counts every signal's filters, and the instance counts are untouched. The signal stats test file passes (7 tests, including the new one).

The fix is in `get_signal_stats` in `src/dispatch/signal/service.py`. When `signal_id` is given, the snooze query is limited to filters linked to that signal through `assoc_signal_filters`.

The new test in `tests/signal/test_signal_stats_service.py` attaches an active filter to one signal and an expired one to another, both matching the same entity. It checks that each signal sees only its own filter and that the no-signal call sees both. I only ran that file, not the full suite.

The snooze count query also doesn't check that a filter's action is snooze, so any expired or active filter matching the entity is counted. I left that as it was since it's outside this bug.