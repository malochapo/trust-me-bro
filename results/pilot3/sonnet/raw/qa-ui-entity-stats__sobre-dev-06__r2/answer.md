The UI calls `GET /signals/stats` with `entity_type_id`, `entity_value` and `num_days=30`. It does not use the per-signal `/signals/{signal_id}/stats` route.

- **Endpoint:** `getStats` in `signal/api.js` builds the request. The entity table in `signal/instance/store.js` calls it for each entity row and passes `STATS_DAYS = 30`. The route is `return_signal_stats` in `signal/views.py`.
- **Function:** `return_signal_stats` calls `get_signal_stats` in `signal/service.py`, which computes all four counts.
- **Scoped to the signal:** No. `return_signal_stats` doesn't pass a `signal_id`, so the counts cover every signal for that entity. Only the unused `/{signal_id}/stats` route filters by signal.
- **Instance window:**
  - The alerted and snoozed instance counts only include instances with `created_at` in the last `num_days` days, which is 30 as the UI calls it.
  - The active and expired snooze counts are not date-limited. They count `SignalFilter` rows whose expression matches the entity, and split on whether the expiration is after the current date.

ENDPOINT: GET /signals/stats
FUNCTION: get_signal_stats
SCOPED_TO_SIGNAL: no
INSTANCE_WINDOW: 30