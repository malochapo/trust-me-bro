The signal instance views fetch these counts through `getStats` in `signal/api.js`. That function calls `GET signals/stats?entity_type_id=…&entity_value=…&num_days=30`. The entity table loader in `signal/instance/store.js` (`getAllEntities`) calls it once per entity row with `STATS_DAYS = 30`. The call goes to `/signals/stats` and not `/signals/{signal_id}/stats`, so no signal id is sent.

- **Endpoint:** `return_signal_stats` in `signal/views.py` handles `GET /stats` and passes `entity_value`, `entity_type_id` and `num_days` to the function below.
- **Function:** `get_signal_stats` in `signal/service.py` computes all four counts.
- **Scoping to the signal:** the counts are not limited to the signal being viewed. This route never passes `signal_id`, and the filter `SignalInstance.signal_id == signal_id if signal_id else True` then matches every signal. A separate `GET /{signal_id}/stats` route does pass it, but this UI does not call it.
- **Alerted and snoozed counts:** they cover signal instances created in the last 30 days (`SignalInstance.created_at >= now - num_days`).
- **Snooze counts:** the active and expired counts have no date limit. They count every signal filter whose expression matches the entity, split by whether `expiration` is after the current date. They are not scoped to a signal either.

ENDPOINT: GET /signals/stats
FUNCTION: get_signal_stats
SCOPED_TO_SIGNAL: no
INSTANCE_WINDOW: 30