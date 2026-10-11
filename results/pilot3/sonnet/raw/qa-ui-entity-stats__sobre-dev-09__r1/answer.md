The signal instance store calls `SignalApi.getStats(entity.entity_type.id, entity.value, STATS_DAYS)` for each entity (`signal/instance/store.js:130`). `getStats` is defined in `signal/api.js`. It hits the unscoped route `GET /signals/stats?entity_type_id=…&entity_value=…&num_days=30`, handled by `return_signal_stats` in `signal/views.py`. That handler calls `get_signal_stats` in `signal/service.py`.

- **Signal scoping:** The UI doesn't pass a `signal_id`, so the counts cover every signal that has this entity. A separate route, `/{signal_id}/stats`, would scope to one signal, but the UI doesn't use it.
- **Instance counts:** `STATS_DAYS = 30` is passed as `num_days`. The alerted and snoozed counts only include signal instances with `created_at` in the last 30 days. Alerted means `filter_action` is not "snooze" or is null. Snoozed means `filter_action` is "snooze".
- **Snooze counts:** The active and expired snooze counts are not date-limited. They come from `SignalFilter` rows whose expression references the entity. A snooze is active if its expiration is after the current date, and expired if it is on or before it. They are also not limited to the signal being viewed.

ENDPOINT: GET /signals/stats
FUNCTION: get_signal_stats
SCOPED_TO_SIGNAL: no
INSTANCE_WINDOW: 30