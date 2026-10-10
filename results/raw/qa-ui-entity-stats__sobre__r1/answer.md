The UI doesn't scope the counts to the signal being viewed, and the instance counts cover the last 30 days.

- **UI call:** `getStats` in `signal/api.js` calls `GET signals/stats` with `entity_type_id`, `entity_value` and `num_days`. The signal instance store (`signal/instance/store.js:127-130`) makes this call once per entity, with `STATS_DAYS = 30`.
- **Backend:** the route `return_signal_stats` in `signal/views.py` calls `get_signal_stats` in `signal/service.py`.
- **Scoping:**
  - The UI uses `/stats`, which passes no `signal_id`, so the counts span all signals for that entity.
  - A separate route, `GET /{signal_id}/stats`, does scope to one signal, but the UI doesn't call it.
- **Window:**
  - The alerted and snoozed instance counts are filtered by `SignalInstance.created_at >= now - num_days`, so they cover the last 30 days.
  - The active and expired snooze counts are not date-limited. They are counted over all signal filters (snoozes) that reference the entity, by whether `expiration` is after today.

ENDPOINT: GET signals/stats
FUNCTION: get_signal_stats
SCOPED_TO_SIGNAL: no
INSTANCE_WINDOW: 30