The UI calls the signal stats endpoint from `getStats` in `signal/api.js`. The store in `signal/instance/store.js:127-130` calls it with `num_days = 30`.

- **Endpoint:** `getStats` requests `${resource}/stats?entity_type_id=…&entity_value=…&num_days=30`. It never passes a signal ID, so it uses the global `GET /signals/stats` route (`return_signal_stats` in `signal/views.py`). A per-signal route, `GET /signals/{signal_id}/stats`, also exists, but the UI doesn't use it.
- **Function:** `get_signal_stats` in `signal/service.py` computes all four counts.
- **Scoping:** `signal_id` is only passed on the per-signal route. The route the UI calls leaves it as `None`, so the counts cover every signal for that entity, not just the one being viewed.
- **Window:** `num_days` filters `SignalInstance.created_at` for the alerted and snoozed instance counts, so those cover the last 30 days. The active and expired snooze counts come from `SignalFilter` rows matching the entity and are not limited by days. Active means the filter's expiration is after the current date, and expired means it is on or before it.

ENDPOINT: GET /signals/stats
FUNCTION: get_signal_stats
SCOPED_TO_SIGNAL: no
INSTANCE_WINDOW: 30