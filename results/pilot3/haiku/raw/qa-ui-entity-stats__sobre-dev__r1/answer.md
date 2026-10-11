The UI gets these counts from `GET /signals/stats`, which is computed by `get_signal_stats`. The entity table calls it without a signal ID, so the counts span all signals, not just the one being viewed. The frontend passes `num_days=30` (`STATS_DAYS` in `src/dispatch/static/dispatch/src/signal/instance/store.js`), so the alerted and snoozed instance counts cover the last 30 days. The active and expired snooze counts are not date-filtered; they come from each filter's expiration date.

A per-signal variant, `GET /signals/{signal_id}/stats`, exists in `src/dispatch/signal/views.py`, but the entity table does not use it.

ENDPOINT: GET /signals/stats
FUNCTION: get_signal_stats
SCOPED_TO_SIGNAL: no
INSTANCE_WINDOW: 30