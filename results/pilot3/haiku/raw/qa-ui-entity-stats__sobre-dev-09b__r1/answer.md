The UI reads these counts from `GET /signals/stats`, computed by `get_signal_stats` in `src/dispatch/signal/service.py`. The counts are not limited to the signal being viewed. The alerted and snoozed instance counts cover the last 30 days, but the active and expired snooze counts have no time window.

- **Caller:** `TableInstanceEntities.vue` renders the entity table in the signal instance view. `store.js` `getAllEntities` calls `SignalApi.getStats(entity_type_id, entity_value, 30)` for each entity, with `STATS_DAYS = 30`. `api.js` builds `/signals/stats?entity_type_id=…&entity_value=…&num_days=30`.
- **Route:** `src/dispatch/signal/views.py` `return_signal_stats` handles `GET /stats`. The router is mounted at `/signals`, and the path relative to the org prefix is `/signals/stats`.
- **Scoping:** The entity table does not pass a `signal_id`. The function only adds a `SignalInstance.signal_id` filter when one is given, so the counts span all signals. The signal-scoped variant `/signals/{signal_id}/stats` exists but this view does not use it.
- **Window:** `get_signal_stats` filters instances with `SignalInstance.created_at >= now - num_days`, so alerted and snoozed instance counts cover 30 days. The active and expired snooze counts come from `SignalFilter.expiration` compared with the current date, with no `num_days` filter.

ENDPOINT: GET /signals/stats
FUNCTION: get_signal_stats
SCOPED_TO_SIGNAL: no
INSTANCE_WINDOW: 30