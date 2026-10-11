The UI calls `GET /signals/stats` through `SignalApi.getStats` in `signal/api.js`. The caller is at `signal/instance/store.js:130`. It passes the entity type id, the entity value and `num_days=30`. The route is `return_signal_stats` in `signal/views.py`, and it calls `get_signal_stats` in `signal/service.py`.

- **Scoped to the signal:** No. The UI never calls the per-signal route `GET /signals/{signal_id}/stats`, which would pass `signal_id` and limit the instance counts to that one signal. `GET /signals/stats` passes no `signal_id`, so the counts cover every signal that has the entity.
- **Instance window:** Alerted and snoozed instance counts only include instances with `created_at` in the last 30 days. The UI sets `STATS_DAYS = 30`.
- **Snooze counts:** The active and expired snooze counts have no date filter. They count every signal filter whose expression references the entity, so they cover all time.

ENDPOINT: GET /signals/stats
FUNCTION: get_signal_stats
SCOPED_TO_SIGNAL: no
INSTANCE_WINDOW: 30