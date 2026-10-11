The UI gets these counts from `GET /signals/stats`, and `get_signal_stats` computes them. The counts are not limited to the signal being viewed, and the alerted and snoozed instance counts cover the last 30 days.

**Endpoint.** The entity table in `signal/instance/store.js` calls `SignalApi.getStats(entity.entity_type.id, entity.value, 30)` once for each entity row. That sends `GET /signals/stats?entity_type_id=…&entity_value=…&num_days=30`. It is handled by `return_signal_stats` in `signal/views.py`.

**Function.** `get_signal_stats` in `signal/service.py` builds the four numbers.
- **Snooze counts:** `num_snoozes_active` and `num_snoozes_expired` count signal filters whose expression matches the entity. Active means the expiration is after today, and expired means it is on or before today. These two counts are not date-limited.
- **Instance counts:** `num_signal_instances_alerted` counts instances with no snooze action. `num_signal_instances_snoozed` counts those with `filter_action == "snooze"`.

**Scope.** The UI call never passes a `signal_id`, so the stats are across all signals for that entity. The backend does have a per-signal route, `GET /{signal_id}/stats`, which would filter by signal. Nothing in the frontend calls it.

**Window.** The store sets `STATS_DAYS = 30` and passes it as `num_days`. The backend turns that into a `created_at >= now - 30 days` filter on the instance counts. Without `num_days` the instance counts would be all time, but the UI always sends 30.

ENDPOINT: GET /signals/stats
FUNCTION: get_signal_stats
SCOPED_TO_SIGNAL: no
INSTANCE_WINDOW: 30