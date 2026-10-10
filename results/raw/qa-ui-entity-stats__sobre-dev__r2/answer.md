The UI calls the signal stats endpoint with no signal id, and the backend counts across all signals for that entity.

- **Endpoint:** `getStats` in `static/dispatch/src/signal/api.js:48` requests `/signals/stats?entity_type_id=…&entity_value=…&num_days=…`. The store (`signal/instance/store.js:127-130`) passes `STATS_DAYS = 30`. The route is `return_signal_stats` in `signal/views.py`.
- **Function:** `return_signal_stats` calls `get_signal_stats` in `signal/service.py:985`.
- **Scoped to the signal:** No. The UI uses the unscoped `/stats` route, so `signal_id` is `None` and the instance counts cover every signal that carries the entity. A separate route, `GET /signals/{signal_id}/stats`, does scope by signal, but the UI doesn't call it.
- **Snooze counts:** The active and expired snooze counts ignore the day window. They count every signal filter whose expression references the entity. A filter is active if its expiration is after today and expired otherwise.
- **Instance window:** The alerted and snoozed counts only include instances created in the last `num_days` days. The UI passes 30. If `num_days` were omitted, the window would be all time.

ENDPOINT: GET /signals/stats
FUNCTION: get_signal_stats
SCOPED_TO_SIGNAL: no
INSTANCE_WINDOW: 30