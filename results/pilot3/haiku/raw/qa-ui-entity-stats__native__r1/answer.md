The UI gets these counts from `GET /signals/stats`, computed by `get_signal_stats`. The counts are not limited to the signal being viewed, and the alerted and snoozed instance counts cover the last 30 days.

- **Endpoint:** the entity table in `src/dispatch/static/dispatch/src/signal/instance/store.js` calls `SignalApi.getStats(entity_type_id, entity_value, 30)`. That builds `GET {resource}/stats?entity_type_id=…&entity_value=…&num_days=30`, where `resource` is `signals` (`src/dispatch/static/dispatch/src/signal/api.js:55`). The route is `return_signal_stats` in `src/dispatch/signal/views.py:285`, mounted under `/{organization}` with the `/signals` prefix (`src/dispatch/api.py:137`).
- **Function:** `get_signal_stats` in `src/dispatch/signal/service.py:985`. It counts snoozed (`filter_action == "snooze"`) and non-snoozed instances linked to the entity. It also counts active and expired snooze filters that match the entity.
- **Scope:** the UI call does not pass `signal_id`, so the instance counts span all signals. The `signal_id` filter exists in the backend, and the separate `/{signal_id}/stats` route uses it, but the entity table does not call that route.
- **Window:** `num_days=30` filters instances by `SignalInstance.created_at >= now - 30 days`. The active and expired snooze counts are not date-windowed. They depend only on each filter's expiration date.

ENDPOINT: GET /signals/stats
FUNCTION: get_signal_stats
SCOPED_TO_SIGNAL: no
INSTANCE_WINDOW: 30