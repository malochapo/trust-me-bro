The UI calls the general stats endpoint, not the per-signal one, so the counts are not limited to the signal being viewed.

- **Endpoint:** `getStats` in `static/dispatch/src/signal/api.js` requests `/signals/stats` with `entity_type_id`, `entity_value` and `num_days`. The handler is `return_signal_stats` in `signal/views.py`. A per-signal route, `/signals/{signal_id}/stats`, also exists, but the UI doesn't call it.
- **Function:** `get_signal_stats` in `signal/service.py` computes the counts. The per-signal route passes it a `signal_id`. The general route does not.
- **Scope:** because the UI uses the general route, the instance counts cover that entity across all signals.
- **Snooze counts:** active and expired snoozes come from `SignalFilter` rows matching the entity. They are not limited by date or signal.
- **Window:** `static/dispatch/src/signal/instance/store.js` sets `STATS_DAYS = 30` and passes it as `num_days`. The alerted and snoozed instance counts therefore only include instances created in the last 30 days.

ENDPOINT: GET /signals/stats
FUNCTION: get_signal_stats
SCOPED_TO_SIGNAL: no
INSTANCE_WINDOW: 30