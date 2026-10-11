The signal instance store (`signal/instance/store.js:127-130`) calls `SignalApi.getStats(entity.entity_type.id, entity.value, 30)` for each entity. That sends `GET /signals/stats?entity_type_id=…&entity_value=…&num_days=30`. The route is `return_signal_stats` in `signal/views.py`.

The route calls `get_signal_stats` in `signal/service.py`.

**Scoping:** The UI never passes a signal ID, so the call is not scoped to the signal being viewed. `signal_id` stays `None` and the instance counts cover every signal for that entity. A separate route, `GET /signals/{signal_id}/stats`, does scope by signal, but the UI doesn't use it.

The snooze counts are also not scoped to a signal or a time window. They come from `SignalFilter` rows whose expression contains the entity. Active means `expiration > current_date`, and expired means `expiration <= current_date`.

**Window:** The alerted and snoozed instance counts only include instances created in the last 30 days (`SignalInstance.created_at >= now - num_days`).
- Alerted counts instances whose `filter_action` is not "snooze" or is null.
- Snoozed counts instances whose `filter_action` is "snooze".

ENDPOINT: GET /signals/stats
FUNCTION: get_signal_stats
SCOPED_TO_SIGNAL: no
INSTANCE_WINDOW: 30