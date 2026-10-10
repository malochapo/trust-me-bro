`GET /{signal_id}/stats` now counts only the snooze filters attached to that signal. All 7 tests in `tests/signal/test_signal_stats_service.py` pass.

- **Fix:** in `get_signal_stats` (`src/dispatch/signal/service.py`), when `signal_id` is given, the snooze query is restricted to filters linked to that signal through `assoc_signal_filters`. `/signals/stats` (no signal) is unchanged and still counts every signal's filters. The instance counts are untouched.
- **Test:** I added `test_get_signal_stats_snooze_counts_scoped_to_signal`. It attaches an active snooze to one signal and an expired snooze to another, both on the same entity. Each signal's stats show only its own snooze, and the stats without a signal show both.

I did not run the test against the old code, so I haven't seen it fail without the fix.