The signal instance view calls `SignalApi.getStats(entity.entity_type.id, entity.value, STATS_DAYS)` in `signal/instance/store.js`. That request goes to `GET signals/stats?entity_type_id=…&entity_value=…&num_days=30`. The route is `return_signal_stats` in `signal/views.py`, and it calls `get_signal_stats` in `signal/service.py`.

- **Signal scope:** The counts are not limited to the signal being viewed. The UI hits the global `/stats` route, which never passes a `signal_id`. A separate `/{signal_id}/stats` route does pass one, but the UI doesn't use it. So the counts cover every signal that has that entity.
- **Window for instance counts:** The alerted and snoozed instance counts only include instances created in the last 30 days (`created_at >= now - num_days`, with `STATS_DAYS = 30`).
- **Window for snoozes:** The active and expired snooze counts are not limited by date. They come from the signal filters whose expression references the entity, split by whether `expiration` is after the current date.

ENDPOINT: GET signals/stats
FUNCTION: get_signal_stats
SCOPED_TO_SIGNAL: no
INSTANCE_WINDOW: 30