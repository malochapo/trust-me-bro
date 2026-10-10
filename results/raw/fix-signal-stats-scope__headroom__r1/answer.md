Fixed: with a `signal_id`, `get_signal_stats` now counts only the snooze filters attached to that signal. Without one, it still counts every signal's filters. The instance counts are untouched.

The change is in `src/dispatch/signal/service.py`. When `signal_id` is given, the snooze-filter query is restricted to filters linked to that signal through `assoc_signal_filters`.

I added `test_get_signal_stats_snooze_counts_scoped_to_signal` to `tests/signal/test_signal_stats_service.py`. It builds two signals with different snooze filters on the same entity and checks per-signal and all-signal counts. It fails without the fix, and all 7 tests in that file pass with it.

I only ran that file, not the full suite.