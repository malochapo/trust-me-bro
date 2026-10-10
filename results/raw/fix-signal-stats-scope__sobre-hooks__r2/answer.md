Fixed: `GET /{signal_id}/stats` now counts only the snooze filters attached to that signal, and `/signals/stats` without a signal still counts every signal's filters. The 7 tests in `tests/signal/test_signal_stats_service.py` pass. I did not run the rest of the suite.

- **Fix:** in `get_signal_stats` (`src/dispatch/signal/service.py`), when `signal_id` is given, the filter query now also requires the filter to be linked to that signal through `assoc_signal_filters`. I added the import for that table.
- **Test:** `test_get_signal_stats_snoozes_scoped_to_signal` (same test file) gives one signal an active snooze filter and another an active plus an expired one. All three match the same entity. It checks the per-signal counts are (1, 0) and (1, 1), and the unscoped count is (2, 1).

The snooze counts include any filter that matches the entity, whether or not its action is "snooze", so a deduplicate filter would be counted too. That wasn't part of the bug report, so I left it alone.