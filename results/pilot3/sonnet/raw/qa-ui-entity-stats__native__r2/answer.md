The signal instance store (`signal/instance/store.js:130`) calls `SignalApi.getStats(entity.entity_type.id, entity.value, STATS_DAYS)`, and `STATS_DAYS` is 30. That request goes to `GET /signals/stats?entity_type_id=…&entity_value=…&num_days=30`, which is handled by `return_signal_stats` in `signal/views.py`. That handler calls `get_signal_stats` in `signal/service.py`.

- **Scoping:** The UI call doesn't pass a `signal_id`, so the counts are not limited to the signal being viewed. They cover all signals for that entity. A separate endpoint, `/{signal_id}/stats`, does scope to one signal, but the UI doesn't use it here.
- **Alerted and snoozed instances:** These are counted over the last 30 days. The filter is `SignalInstance.created_at >= now - num_days`. Alerted means `filter_action` is not "snooze" (or is null). Snoozed means `filter_action == "snooze"`.
- **Active and expired snoozes:** The snooze counts are not date-limited. They count every `SignalFilter` whose expression references the entity, split by `expiration` against the current date.

ENDPOINT: GET /signals/stats
FUNCTION: get_signal_stats
SCOPED_TO_SIGNAL: no
INSTANCE_WINDOW: 30