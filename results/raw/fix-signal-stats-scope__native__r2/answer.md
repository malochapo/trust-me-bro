`GET /{signal_id}/stats` now counts only the snooze filters attached to that signal. `GET /signals/stats`, without a signal, still counts the filters of every signal. The stats tests pass (7 in `tests/signal/test_signal_stats_service.py`), but I did not run the rest of the suite.

The fix is in `get_signal_stats` in `src/dispatch/signal/service.py`. When `signal_id` is given, the snooze-filter query is limited to filters linked to that signal through the `assoc_signal_filters` table. I also added the `assoc_signal_filters` import there.

The new test, `test_get_signal_stats_snoozes_scoped_to_signal`, attaches an active snooze filter to one signal and an expired one to another, both matching the same entity. It checks these counts:

| Call | Active | Expired |
|---|---|---|
| First signal | 1 | 0 |
| Second signal | 0 | 1 |
| No signal | 1 | 1 |