The UI gets these counts from `GET /signals/stats`, computed by `get_signal_stats`. The counts are not limited to the signal being viewed, and the alerted and snoozed instance counts cover the last 30 days.

- **Caller:** `getAllEntities` in `src/dispatch/static/dispatch/src/signal/instance/store.js:116` fetches each entity row, then calls `SignalApi.getStats(entity_type_id, entity_value, 30)` (`STATS_DAYS = 30`, line 127). The entity table is rendered by `TableInstanceEntities.vue`.
- **Endpoint:** `SignalApi.getStats` in `src/dispatch/static/dispatch/src/signal/api.js:48` builds `/signals/stats?entity_type_id=…&entity_value=…&num_days=30`. The router is mounted at `/signals` (`src/dispatch/api.py:137`) and the whole API sits under `/api/v1` (`src/dispatch/main.py:268`). The handler is `return_signal_stats` in `src/dispatch/signal/views.py:285`.
- **Computation:** `get_signal_stats` in `src/dispatch/signal/service.py:977` computes all four numbers.
  - Alerted and snoozed are counts of `SignalInstance` rows linked to the entity, split by `filter_action == "snooze"`. The date filter is `SignalInstance.created_at >= now - num_days`.
  - Active and expired snoozes count `SignalFilter` rows whose expression matches the entity, split by whether `expiration` is past today. These are not date-windowed.
- **Signal scoping:** `signal_id` is only applied when the caller passes it. The UI does not pass it, so the counts span all signals. The per-signal endpoint `/signals/{signal_id}/stats` exists, but this view does not call it.

ENDPOINT: GET /signals/stats
FUNCTION: get_signal_stats
SCOPED_TO_SIGNAL: no
INSTANCE_WINDOW: 30