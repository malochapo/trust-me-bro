The UI calls `GET /signals/stats` with `entity_type_id`, `entity_value` and `num_days=30`. It does not call the per-signal route `GET /signals/{signal_id}/stats`.

- **UI call:** `SignalApi.getStats` in `signal/api.js` builds the `/stats` URL. `signal/instance/store.js` calls it with `STATS_DAYS = 30` for each entity.
- **Backend:** the `return_signal_stats` handler in `signal/views.py` passes the request to `get_signal_stats` in `signal/service.py`. That function computes the counts. It queries the signal filters for the active and expired snoozes. It queries the signal instances for the alerted and snoozed counts.
- **Signal scope:** the UI's request does not pass a `signal_id`, so the counts are not limited to the signal being viewed. They cover every signal that has that entity. `get_signal_stats` only filters by signal when `signal_id` is set. Only the unused per-signal route sets it.
- **Period:** the alerted and snoozed instance counts only include instances created in the last 30 days (`SignalInstance.created_at >= now - num_days`). The active and expired snooze counts are not date-limited. They count every filter whose expression matches the entity, split by whether its expiration is after today.

ENDPOINT: GET /signals/stats
FUNCTION: get_signal_stats
SCOPED_TO_SIGNAL: no
INSTANCE_WINDOW: 30