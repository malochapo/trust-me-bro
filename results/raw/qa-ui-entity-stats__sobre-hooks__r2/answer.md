The signal instance views get these counts from the unscoped stats endpoint, and the counts are not limited to the signal being viewed.

- **Endpoint:** In `signal/instance/store.js:130`, the UI calls `SignalApi.getStats(entity.entity_type.id, entity.value, STATS_DAYS)`. That sends `GET /signals/stats?entity_type_id=…&entity_value=…&num_days=30`. It does not use the per-signal `/{signal_id}/stats` route.
- **Function:** The handler `return_signal_stats` in `signal/views.py` calls `get_signal_stats` in `signal/service.py`.
- **Scope:** The handler does not pass `signal_id`, so it stays `None`. The `SignalInstance.signal_id` filter is therefore skipped, and the counts cover every signal that has that entity.
- **Window:** `STATS_DAYS` is 30, so the alerted and snoozed instance counts only include instances with `created_at` in the last 30 days. The active and expired snooze counts have no date window. They count all snooze filters whose expression references that entity, split by whether `expiration` is after or on/before the current date.

ENDPOINT: GET /signals/stats
FUNCTION: get_signal_stats
SCOPED_TO_SIGNAL: no
INSTANCE_WINDOW: 30