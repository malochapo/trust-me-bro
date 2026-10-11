The UI calls `GET /signals/stats` and gets back counts for all signals, not just the one being viewed. The instance counts cover the last 30 days, and the snooze active/expired counts have no time window.

- **Endpoint:** the entity table in `src/dispatch/static/dispatch/src/signal/instance/store.js:127-130` calls `SignalApi.getStats(entity.entity_type.id, entity.value, 30)`. That builds `/signals/stats?entity_type_id=…&entity_value=…&num_days=30` (`src/dispatch/static/dispatch/src/signal/api.js:48-56`). The `/api/v1` prefix is mounted in `src/dispatch/main.py:268`. The route is `return_signal_stats` in `src/dispatch/signal/views.py:285-299`. The per-signal route `/signals/{signal_id}/stats` exists, but this UI path doesn't call it.
- **Function:** `get_signal_stats` in `src/dispatch/signal/service.py:985`. It only adds a `SignalInstance.signal_id` filter when `signal_id` is passed, and this path doesn't pass it.
- **Scope:** the query matches on the entity's value and type across all signal instances. `signal_id` is `None` here, so it is not scoped to the signal being viewed.
- **Window:** `num_signal_instances_alerted` and `num_signal_instances_snoozed` count only instances with `created_at` within `num_days` (30 here). Alerted means `filter_action` is not `"snooze"` (or is null), and snoozed means it is `"snooze"`. The active and expired snooze counts come from `SignalFilter` rows matching the entity, split by whether `expiration` is after the current date. Those are not filtered by the 30-day window.

ENDPOINT: GET /signals/stats
FUNCTION: get_signal_stats
SCOPED_TO_SIGNAL: no
INSTANCE_WINDOW: 30 days