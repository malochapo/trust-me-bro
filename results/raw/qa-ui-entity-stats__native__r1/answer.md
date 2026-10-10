The signal instance views call `GET /signals/stats` with `entity_type_id`, `entity_value` and `num_days=30`. The call is `SignalApi.getStats` in `signal/instance/store.js`. The route is `return_signal_stats` in `signal/views.py`, and it calls `get_signal_stats` in `signal/service.py`.

- **Scoping to the signal:** The UI does not use the per-signal route `/signals/{signal_id}/stats`. The route it calls never passes a `signal_id`, so the counts are across all signals for that entity, not just the one being viewed.
- **Alerted and snoozed counts:** These count signal instances linked to the entity whose `created_at` falls within the last 30 days. Instances with `filter_action` of "snooze" count as snoozed. All others count as alerted.
- **Snooze counts:** The active and expired snooze counts are not limited by the 30-day window. They are counted over all signal filters whose expression matches the entity. A snooze is active if its expiration is after the current date and expired otherwise.

ENDPOINT: GET /signals/stats
FUNCTION: get_signal_stats
SCOPED_TO_SIGNAL: no
INSTANCE_WINDOW: 30