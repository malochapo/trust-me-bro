The UI calls `GET /signals/stats` and passes `entity_type_id`, `entity_value` and `num_days=30`. The call is `SignalApi.getStats` in `signal/api.js`, made from `getAllEntities` in `signal/instance/store.js`. The route is `return_signal_stats` in `signal/views.py:285`, and it calls `get_signal_stats` in `signal/service.py:985`.

**Scope to the signal:** no. The UI never passes a signal id, so `signal_id` is `None` and the instance counts cover every signal that has the entity. A separate route, `GET /signals/{signal_id}/stats`, would scope them, but the UI doesn't call it.

**Alerted and snoozed instance counts:**
- The alerted and snoozed counts only include signal instances whose `created_at` falls within the last `num_days` days. The store sets `STATS_DAYS = 30`, so that is 30 days.
- Alerted means `filter_action` is not `snooze` or is null. Snoozed means `filter_action` is `snooze`.

**Snooze counts:** the active and expired counts have no date window and are not scoped to a signal. They count `SignalFilter` rows whose expression references the entity, split by whether `expiration` is after today or on or before today.

ENDPOINT: GET /signals/stats
FUNCTION: get_signal_stats
SCOPED_TO_SIGNAL: no
INSTANCE_WINDOW: 30