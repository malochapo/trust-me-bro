The UI calls `GET /signals/stats` with `num_days=30`, which runs `get_signal_stats` in `src/dispatch/signal/service.py`. That call is not limited to the signal being viewed. The alerted and snoozed instance counts cover the last 30 days, but the active and expired snooze counts do not use that window.

- **Endpoint:** the UI's `SignalApi.getStats` (`src/dispatch/static/dispatch/src/signal/api.js:48`) hits `/signals/stats`, and the store (`src/dispatch/static/dispatch/src/signal/instance/store.js:127-130`) passes `STATS_DAYS = 30`. The route is in `src/dispatch/signal/views.py:285`. The per-signal route `/{signal_id}/stats` exists, but no UI code calls it.
- **Scope:** the global route never passes `signal_id`, so the instance count query covers instances of every signal linked to the entity. Only the per-signal route sets `signal_id`.
- **Window:** `num_days` sets `SignalInstance.created_at >= now - 30 days`. The snooze counts come from `SignalFilter` rows matched by expression and are split on `expiration` against the current date, with no date window.

ENDPOINT: GET /signals/stats
FUNCTION: get_signal_stats
SCOPED_TO_SIGNAL: no
INSTANCE_WINDOW: 30