The UI calls `GET /signals/stats` through `SignalApi.getStats` in `signal/api.js`. The call is made from `signal/instance/store.js` and passes `entity_type_id`, `entity_value` and `num_days=30`. The route is `return_signal_stats` in `signal/views.py`, and it calls `get_signal_stats` in `signal/service.py`.

- **Not limited to the signal being viewed.** The UI never passes a signal id. The route that would scope to one signal, `/{signal_id}/stats`, exists but the UI doesn't use it. `get_signal_stats` then only filters by signal when it is given a `signal_id`.
- **Alerted and snoozed counts cover 30 days.** They count signal instances for the entity whose `created_at` falls in the last 30 days. Instances with `filter_action == "snooze"` count as snoozed. All others count as alerted.
- **Snooze counts have no time window.** The active and expired snooze counts come from signal filters that match the entity, and they are not limited by `num_days` either. Active means the filter's expiration is after today, and expired means it is on or before today.

ENDPOINT: GET /signals/stats
FUNCTION: get_signal_stats
SCOPED_TO_SIGNAL: no
INSTANCE_WINDOW: 30