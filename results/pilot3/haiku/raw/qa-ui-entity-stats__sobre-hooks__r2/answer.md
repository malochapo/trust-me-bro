The UI gets these counts from `GET /signals/stats`, which is called once per entity from the entity table. Both the alerted and snoozed instance counts cover the last 30 days. The snooze active/expired counts are not time-bounded.

- **Caller:** `getAllEntities` in `src/dispatch/static/dispatch/src/signal/instance/store.js` (around line 127) sets `STATS_DAYS = 30` and calls `SignalApi.getStats(entity_type_id, entity_value, 30)`, which requests `/signals/stats` (`src/dispatch/static/dispatch/src/signal/api.js:48`). The table is `TableInstanceEntities.vue`.
- **Backend:** the route `return_signal_stats` in `src/dispatch/signal/views.py:285` calls `get_signal_stats` in `src/dispatch/signal/service.py:985`.
- **Scope:** `get_signal_stats` only filters by `signal_id` when one is passed, and this route never passes it. The counts therefore cover all signals for the entity. The per-signal route `/signals/{signal_id}/stats` is a different endpoint that the entity table does not use.
- **Window:** `num_days=30` becomes a `SignalInstance.created_at >= now - 30 days` filter, and it applies only to the instance counts. The snooze counts come from `SignalFilter.expiration` compared with the current date, with no time window.

ENDPOINT: GET /signals/stats
FUNCTION: get_signal_stats
SCOPED_TO_SIGNAL: no
INSTANCE_WINDOW: 30