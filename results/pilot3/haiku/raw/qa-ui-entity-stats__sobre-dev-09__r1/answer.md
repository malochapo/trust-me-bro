The UI calls `GET /signals/stats`, which goes to `get_signal_stats` in `src/dispatch/signal/service.py`. The counts are not limited to the signal being viewed. The instance store calls `SignalApi.getStats(entity_type.id, value, 30)` without a signal ID, so the backend's `signal_id` filter is never applied. The alerted and snoozed instance counts cover the last 30 days, filtered on `SignalInstance.created_at`. The active and expired snooze counts come from `SignalFilter` expirations and have no time window.

Relevant code:
- `src/dispatch/static/dispatch/src/signal/instance/store.js:127-150` builds the per-entity stats with `STATS_DAYS = 30`.
- `src/dispatch/static/dispatch/src/signal/api.js:48-56` builds `/signals/stats?entity_type_id=…&entity_value=…&num_days=30`.
- `src/dispatch/signal/views.py:285-299` is the `/stats` route. It calls `get_signal_stats` with `signal_id=None`. The per-signal route `/{signal_id}/stats` exists but the UI does not use it.
- `src/dispatch/signal/service.py:985-1061` holds the computation.

ENDPOINT: GET /signals/stats
FUNCTION: get_signal_stats
SCOPED_TO_SIGNAL: no
INSTANCE_WINDOW: 30