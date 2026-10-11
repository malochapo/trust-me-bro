When a signal id is given, `get_signal_stats` now counts only the snooze filters attached to that signal. Without a signal id it still counts every signal's snooze filters. The signal test suite passes (33 passed, 1 skipped), and the new test fails on the original code.

**Cause:** the snooze-filter query in `src/dispatch/signal/service.py` matched filters by entity only and never looked at `signal_id`. Instance counts were already scoped correctly, so I left them alone.

**Fix:** when `signal_id` is set, the query now also requires the filter to appear in `assoc_signal_filters` for that signal. I imported that association table into the service.

**Test:** `test_get_signal_stats_snoozes_scoped_to_signal_id` in `tests/signal/test_signal_stats_service.py` puts an active snooze filter on one signal and an expired one on another, both matching the same entity. It checks that scoping to each signal returns only its own filter, and that the unscoped call returns both.

Not changed: the snooze query doesn't check `action == snooze`, so it counts any filter matching the entity, not only snooze-action ones. That's outside this bug, but it may be worth a look.