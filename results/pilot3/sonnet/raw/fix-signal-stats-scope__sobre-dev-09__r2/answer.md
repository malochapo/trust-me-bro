Fixed. With a `signal_id`, the stats endpoint now counts only the snooze filters attached to that signal. Without one, `/signals/stats` still counts every signal's filters. The signal tests pass (33 passed, 1 skipped), and the new test fails without the fix.

The change is in `get_signal_stats` in `src/dispatch/signal/service.py`. When a `signal_id` is given, the snooze-filter query is restricted to filters linked to that signal through the `assoc_signal_filters` table. The instance counts are untouched.

The new test, `test_get_signal_stats_snoozes_scoped_to_signal` in `tests/signal/test_signal_stats_service.py`, gives two signals one filter each (one active, one expired) for the same entity. It checks 1 active and 1 expired with no signal, then 1 active and 0 expired for the first signal. For the second signal it expects 0 active and 1 expired.

I didn't commit anything.