Fixed: `/signals/{signal_id}/stats` now counts only the snooze filters attached to that signal. `/signals/stats` still counts the filters of every signal. The new test and the existing tests in `tests/signal/test_signal_stats_service.py` all pass (7 passed).

- **Fix:** `get_signal_stats` in `src/dispatch/signal/service.py` now restricts the snooze counts to filters linked to that signal through the `assoc_signal_filters` table. The view already passed `signal_id` through. The instance counts weren't touched.
- **Test:** `test_get_signal_stats_snoozes_scoped_to_signal` gives two signals their own active and expired snooze filters for the same entity. It checks the counts per signal (1 active and 1 expired for one, 2 active and 1 expired for the other). It also checks the unscoped call (3 active and 2 expired).

I ran only that test file, not the whole suite.