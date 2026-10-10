Fixed: `GET /{signal_id}/stats` now counts only the snooze filters attached to that signal. `GET /signals/stats` still counts the snooze filters of every signal. The signal stats test file passes, including the new test.

The fix is in `get_signal_stats` in `src/dispatch/signal/service.py`. When `signal_id` is given, the snooze count query now only includes filters linked to that signal through `assoc_signal_filters`. I didn't touch the instance counts.

The new test is `test_get_signal_stats_snoozes_scoped_to_signal` in `tests/signal/test_signal_stats_service.py`. It gives two signals three snooze filters for the same entity: one active on signal 1, and one active plus one expired on signal 2. It then checks the counts:

| Query | Active | Expired |
|---|---|---|
| No signal | 2 | 1 |
| Signal 1 | 1 | 0 |
| Signal 2 | 1 | 1 |

I only ran `tests/signal/test_signal_stats_service.py`, not the full suite.