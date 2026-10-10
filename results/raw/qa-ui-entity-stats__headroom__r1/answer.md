The UI calls the signal-wide stats endpoint, and the counts are not limited to the signal being viewed.

- **Endpoint:** `getStats` in `static/dispatch/src/signal/api.js` calls `${resource}/stats` with `entity_type_id`, `entity_value` and `num_days`. The caller in `signal/instance/store.js:130` passes `STATS_DAYS = 30`. The route is `return_signal_stats` in `signal/views.py:285`. A separate `/{signal_id}/stats` route exists (`return_single_signal_stats`), but the UI doesn't use it.
- **Function:** `return_signal_stats` calls `get_signal_stats` in `signal/service.py:985`.
- **Scope:** The UI route never passes `signal_id`, so `get_signal_stats` skips its signal filter. Instances are counted across all signals that share the entity. The snooze counts are never filtered by signal. They come from every `SignalFilter` whose expression references the entity, and `num_days` doesn't limit them either.
- **Window:** The alerted and snoozed instance counts only include instances with `created_at` in the last 30 days. Alerted means `filter_action` is not "snooze" or is null.

ENDPOINT: GET /signals/stats
FUNCTION: get_signal_stats
SCOPED_TO_SIGNAL: no
INSTANCE_WINDOW: 30