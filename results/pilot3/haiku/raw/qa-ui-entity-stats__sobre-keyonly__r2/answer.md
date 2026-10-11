The entity rows in the signal instance view get their counts from `GET /signals/stats`, which calls `get_signal_stats` in `src/dispatch/signal/service.py`. The counts are not limited to the signal being viewed: the UI never passes a signal ID, so the instance counts span all signals. The alerted and snoozed instance counts cover the last 30 days, set by `STATS_DAYS = 30` in `src/dispatch/static/dispatch/src/signal/instance/store.js`. The active and expired snooze counts are not date-windowed, so they cover all time.

The chain:
- `TableInstanceEntities.vue` renders the "Signal Triggers" and "Snooze Filters" columns from `instanceStats` and `snoozeStats`.
- The `getAllEntities` action in `store.js` calls `SignalApi.getStats(entity_type_id, value, 30)` for each entity. That method in `src/dispatch/signal/api.js` requests `/signals/stats` with `entity_type_id`, `entity_value`, and `num_days`.
- The backend route `return_signal_stats` in `src/dispatch/signal/views.py` calls `get_signal_stats` with no `signal_id`.
- Inside `get_signal_stats`, the instance counts filter on `SignalInstance.signal_id` only when a signal ID is given, and `created_at >= now - num_days` applies to them. The snooze counts query `SignalFilter` rows matching the entity and bucket them by `expiration` against the current date, with no `num_days` filter.

The per-signal variant `GET /signals/{signal_id}/stats` exists, but the entity table does not use it.

ENDPOINT: GET /signals/stats
FUNCTION: get_signal_stats
SCOPED_TO_SIGNAL: no
INSTANCE_WINDOW: 30