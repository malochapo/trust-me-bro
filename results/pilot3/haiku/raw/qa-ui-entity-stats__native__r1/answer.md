The entity table in the signal instance view calls the unscoped stats endpoint, so the counts span all signals, not just the one being viewed.

- **Frontend:** `TableInstanceEntities.vue` renders `num_signal_instances_alerted`, `num_signal_instances_snoozed`, and `num_snoozes_expired`. The data comes from `fetchSignalStats` in `src/dispatch/static/dispatch/src/signal/instance/store.js` (around line 128), which calls `SignalApi.getStats(entity_type_id, value, 30)` in `src/dispatch/static/dispatch/src/signal/api.js`. That request goes to `/signals/stats` with `entity_type_id`, `entity_value`, and `num_days=30`. It does not send a `signal_id`.
- **Backend:** `GET /signals/stats` (`return_signal_stats` in `src/dispatch/signal/views.py`) calls `get_signal_stats` in `src/dispatch/signal/service.py`. The per-signal variant `GET /signals/{signal_id}/stats` also exists, but this view doesn't use it.
- **Scope:** `signal_id` is optional in `get_signal_stats`, and the UI never passes it, so the alerted and snoozed counts cover every signal instance linked to the entity.
- **Period:** `num_days=30` filters the alerted and snoozed instance counts on `SignalInstance.created_at`. The active and expired snooze counts come from `SignalFilter` rows and are not filtered by that window.

ENDPOINT: GET /signals/stats
FUNCTION: get_signal_stats
SCOPED_TO_SIGNAL: no
INSTANCE_WINDOW: 30