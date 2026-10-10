The signal instance store (`signal/instance/store.js:130`) calls `SignalApi.getStats(entity.entity_type.id, entity.value, 30)`. That sends `GET /signals/stats?entity_type_id=…&entity_value=…&num_days=30`, which is handled by `return_signal_stats` in `signal/views.py`. That handler calls `get_signal_stats` in `signal/service.py`.

- **Signal scoping:** The UI uses the global `/signals/stats` route, which doesn't pass a `signal_id`. The counts are therefore across all signals for that entity, not just the signal being viewed. A separate `/signals/{signal_id}/stats` route does scope to one signal, but the UI doesn't call it.
- **Alerted and snoozed instance counts:** These are filtered by `SignalInstance.created_at >= now - num_days`. The UI passes `STATS_DAYS = 30`, so the window is the last 30 days.
- **Snooze counts:** The active and expired snooze counts come from `SignalFilter` rows that match the entity. They are not date-limited and are not tied to a signal.

ENDPOINT: GET /signals/stats
FUNCTION: get_signal_stats
SCOPED_TO_SIGNAL: no
INSTANCE_WINDOW: 30