Fixed: `get_signal_stats` in `src/dispatch/signal/service.py` now counts only the snooze filters attached to the given signal when a `signal_id` is passed. With no `signal_id`, it still counts every signal's filters.

`SignalFilter` has no `signal_id` column. The link between signals and filters is the `assoc_signal_filters` table, so the new filter selects through that table.

I added `test_get_signal_stats_snoozes_scoped_to_signal` to `tests/signal/test_signal_stats_service.py`. It gives one signal an active snooze and another an expired snooze for the same entity. It then checks each signal sees only its own count, and that the call without a signal sees both. The whole file passes (7 tests); I didn't run the rest of the suite.