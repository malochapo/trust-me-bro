The UI gets these counts from `GET /signals/stats`. The call is `SignalApi.getStats` in `static/dispatch/src/signal/api.js`. It is made from `static/dispatch/src/signal/instance/store.js:130`, once per entity, and passes `entity_type_id`, `entity_value` and `num_days=30`.

- **Backend handler:** the route is `return_signal_stats` in `signal/views.py`. It calls `get_signal_stats` in `signal/service.py`.
- **Scoping:** the counts are not limited to the signal being viewed. The UI doesn't use the `/{signal_id}/stats` route, which does scope by signal. The route it calls never passes `signal_id`, so the alerted and snoozed instance counts cover every signal that has that entity.
- **Instance window:** the alerted and snoozed instance counts only include instances created in the last 30 days (`SignalInstance.created_at >= now - num_days`).
- **Snooze counts:** the active and expired snooze counts have no date window. They come from `SignalFilter` rows whose expression references the entity, split by whether the expiration is after or on/before the current date.

ENDPOINT: GET /signals/stats
FUNCTION: get_signal_stats
SCOPED_TO_SIGNAL: no
INSTANCE_WINDOW: 30