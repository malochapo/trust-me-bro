The UI gets these counts from `GET /signals/stats`, computed by `get_signal_stats`. The counts are not scoped to one signal, and the alerted and snoozed instance counts cover the last 30 days.

- **Endpoint:** The entity table in the signal instance view (`store.js` `getAllEntities`) calls `SignalApi.getStats(entity_type_id, entity_value, 30)` for each entity. That goes to `GET /signals/stats` (`api.js:48`), handled by `return_signal_stats` in `src/dispatch/signal/views.py:284`.
- **Function:** `get_signal_stats` in `src/dispatch/signal/service.py:988`.
- **Scope:** The signal-specific route `/signals/{signal_id}/stats` exists, but this view doesn't use it. The `/stats` route passes no `signal_id`, so the filter on `SignalInstance.signal_id` is skipped and counts cover all signals.
- **Window:** The frontend sets `STATS_DAYS = 30` and passes it as `num_days`. The backend filters only instance counts by `SignalInstance.created_at`. Snooze active and expired counts come from `SignalFilter.expiration` and ignore the window.

ENDPOINT: GET /signals/stats
FUNCTION: get_signal_stats
SCOPED_TO_SIGNAL: no
INSTANCE_WINDOW: 30