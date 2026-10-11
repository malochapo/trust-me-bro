The entity table in the signal instance view fills its count columns from one call per entity, and that call is not scoped to a signal.

- **Endpoint:** the UI calls `SignalApi.getStats` (`src/dispatch/static/dispatch/src/signal/api.js:48`), which issues `GET /signals/stats?entity_type_id=…&entity_value=…&num_days=…` to the `/api/v1` API prefix. The route is `return_signal_stats` in `src/dispatch/signal/views.py:285`.
- **Function:** `get_signal_stats` in `src/dispatch/signal/service.py:985`.
- **Scope:** the entity table's `getAllEntities` action (`src/dispatch/static/dispatch/src/signal/instance/store.js`) passes no `signal_id`, so the counts cover every signal. The per-signal route `/signals/{signal_id}/stats` exists, but this view does not use it.
- **Period:** the store sets `STATS_DAYS = 30` and sends it as `num_days`. The alerted and snoozed instance counts are filtered to `SignalInstance.created_at` within the last 30 days. The active and expired snooze counts come from `SignalFilter` rows and are not limited by that window.

ENDPOINT: GET /signals/stats
FUNCTION: get_signal_stats
SCOPED_TO_SIGNAL: no
INSTANCE_WINDOW: 30