The UI gets these counts from the signal-wide stats endpoint, not the per-signal one. The counts are not limited to the signal being viewed. The alerted and snoozed instance counts cover the last 30 days.

- **Endpoint:** `getStats` in `static/dispatch/src/signal/api.js` calls `signal/stats?entity_type_id=…&entity_value=…&num_days=…`. It does not call the per-signal route `/{signal_id}/stats`. The store (`signal/instance/store.js:127-130`) calls it with `STATS_DAYS = 30`. The route is `return_signal_stats` in `signal/views.py`.
- **Function:** `return_signal_stats` calls `get_signal_stats` in `signal/service.py`.
- **Scoping:** the UI never passes a signal ID, so `signal_id` is `None`. The instance query therefore matches the entity across all signals. The per-signal route would pass the ID, but the UI doesn't use it.
- **Instance window:** alerted and snoozed instance counts only include instances whose `created_at` falls within the last `num_days` days, which is 30 from the UI. The snooze counts are different: active and expired snoozes come from signal filters matching the entity, with no date window. They are also not restricted to the viewed signal.

ENDPOINT: GET /signals/stats
FUNCTION: get_signal_stats
SCOPED_TO_SIGNAL: no
INSTANCE_WINDOW: 30