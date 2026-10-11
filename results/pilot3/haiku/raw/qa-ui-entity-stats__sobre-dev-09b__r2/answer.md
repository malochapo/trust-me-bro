The entity table in the signal instance view calls `GET /signals/stats` through `SignalApi.getStats` with `STATS_DAYS = 30`. The backend computes the counts in `get_signal_stats`, which only filters by signal when a `signal_id` is passed, and the UI never passes one. Alerted and snoozed instance counts cover the last 30 days (`SignalInstance.created_at >= now - 30 days`). The active and expired snooze counts come from `SignalFilter` rows and are not limited to that window.

Key locations:
- `src/dispatch/static/dispatch/src/signal/instance/store.js:126-130` sets `STATS_DAYS = 30` and fetches stats per entity.
- `src/dispatch/static/dispatch/src/signal/api.js:48-60` builds `/signals/stats?entity_type_id=…&entity_value=…&num_days=30`.
- `src/dispatch/signal/views.py:285-299` is the `/stats` route (`return_signal_stats`), which calls `get_signal_stats`.
- `src/dispatch/signal/service.py:985-1062` is `get_signal_stats`. The `signal_id` filter there is optional, and the date threshold applies only to the instance counts.

ENDPOINT: GET /signals/stats
FUNCTION: get_signal_stats
SCOPED_TO_SIGNAL: no
INSTANCE_WINDOW: 30