The UI gets these counts from `GET /signals/stats`, and `get_signal_stats` computes them.

**How the UI calls it.** The entity table in `signal/instance/store.js` (`getAllEntities`) calls `SignalApi.getStats(entity.entity_type.id, entity.value, 30)` once for each entity row. That call is the only use of `getStats` in the frontend. It sends `entity_type_id`, `entity_value` and `num_days=30` as query parameters, and no signal ID.

**Backend.** The route is `return_signal_stats` in `signal/views.py`. It calls `get_signal_stats` in `signal/service.py`. A separate `/{signal_id}/stats` route exists and passes a `signal_id`, but the UI never calls it.

**Scoping.** The counts are not limited to the signal being viewed. The UI doesn't pass a signal ID, so `get_signal_stats` runs with `signal_id=None`. The alerted and snoozed counts then cover instances from every signal that carry that entity. The snooze counts are never filtered by signal. They count every `SignalFilter` whose expression references the entity, split into active (expiration after today) and expired.

**Period.**
- **Alerted and snoozed instance counts:** limited to `SignalInstance.created_at >= now - num_days`, and the UI sends 30, so the last 30 days.
- **Active and expired snooze counts:** not time-windowed. They are based on each filter's expiration date relative to today.

ENDPOINT: GET /signals/stats
FUNCTION: get_signal_stats
SCOPED_TO_SIGNAL: no
INSTANCE_WINDOW: 30