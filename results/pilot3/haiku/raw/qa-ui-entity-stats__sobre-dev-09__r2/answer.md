The UI calls `GET /signals/stats` through `SignalApi.getStats` (`src/dispatch/static/dispatch/src/signal/api.js:48`). The entity table requests it for each entity with `num_days=30`, and the response fills `snoozeStats` and the alerted/snoozed counts in `src/dispatch/static/dispatch/src/signal/instance/store.js:127-153`. The endpoint is `return_signal_stats` in `src/dispatch/signal/views.py:285`, which calls `get_signal_stats` in `src/dispatch/signal/service.py:985`.

- **Scope:** The UI never passes a signal ID, so the call takes the unscoped path. Counts cover all signals that touch the entity. Only the `/{signal_id}/stats` variant filters by signal, and the UI doesn't use it.
- **Window:** The alerted and snoozed instance counts use `SignalInstance.created_at >= now - 30 days`. The snooze active and expired counts come from `SignalFilter` rows matching the entity, with no date window. Those counts split on whether `expiration` is after the current date.

ENDPOINT: GET /signals/stats
FUNCTION: get_signal_stats
SCOPED_TO_SIGNAL: no
INSTANCE_WINDOW: 30