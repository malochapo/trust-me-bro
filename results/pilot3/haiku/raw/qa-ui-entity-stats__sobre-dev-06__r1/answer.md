The entity table in the signal instance view calls `SignalApi.getStats` with `STATS_DAYS = 30`, which hits the global `/signals/stats` endpoint with no `signal_id`. So the counts span all signals, and the alerted and snoozed instance counts cover the last 30 days. The snooze active/expired counts are not time-bounded.

- **Endpoint:** the frontend resource is `/signals` (`src/dispatch/static/dispatch/src/signal/api.js:3`), and `getStats` calls `${resource}/stats` (line 55). The route is `return_signal_stats` in `src/dispatch/signal/views.py:285`. A per-signal variant, `/{signal_id}/stats` (line 302), exists but nothing in the UI calls it.
- **Computation:** `get_signal_stats` in `src/dispatch/signal/service.py` (around lines 987–1061). It counts instances by `filter_action == "snooze"` vs. everything else, filtered by `created_at >= now - num_days`. It counts active vs. expired snooze filters from `SignalFilter.expiration` with no date window.
- **Scope:** `signal_id` is only applied when provided, and the entity table does not provide it, so the counts are not limited to the signal being viewed.

ENDPOINT: GET /signals/stats
FUNCTION: get_signal_stats
SCOPED_TO_SIGNAL: no
INSTANCE_WINDOW: 30