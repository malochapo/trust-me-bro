Fixed: when you pass a signal id, the snooze counts now include only the filters attached to that signal. The stats tests pass, including the new one.

The change is in `get_signal_stats` in `src/dispatch/signal/service.py`. When `signal_id` is given, the snooze-count query now keeps only filters linked to that signal through `assoc_signal_filters`. Without a `signal_id` it still counts every signal's filters, as before.

I added `test_get_signal_stats_snoozes_scoped_to_signal` to `tests/signal/test_signal_stats_service.py`. It attaches an active filter to one signal and an expired filter to another, both matching the same entity. Each signal reports only its own filter, and the no-signal call reports both.

I only ran `tests/signal/test_signal_stats_service.py`, not the full suite.

The snooze query never checked that a filter's action is "snooze", so it counts any filter that matches the entity, deduplicate filters included. I left that alone since you didn't report it, but it's probably worth a look.