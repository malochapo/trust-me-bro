The signal instance view calls `SignalApi.getStats` (`signal/api.js`) from `signal/instance/store.js:130`. That function sends `GET /signals/stats?entity_type_id=…&entity_value=…&num_days=30`. It does not use the per-signal route `/signals/{signal_id}/stats`.

The route `return_signal_stats` in `signal/views.py` hands off to `get_signal_stats` in `signal/service.py`. That function computes both kinds of count:
- **Snoozes:** active and expired snooze counts come from `SignalFilter` rows that reference the entity. Active means the expiration is after today, and expired means it is today or earlier. This part has no date window.
- **Instances:** alerted and snoozed instance counts come from `SignalInstance` rows linked to the entity. Snoozed means `filter_action == "snooze"`, and alerted means everything else.

**Scoping:** the counts are not limited to the signal being viewed. The UI never passes a `signal_id`, so `get_signal_stats` skips its signal filter and counts across all signals for that entity. The snooze counts never had a signal filter in either case.

**Window:** the UI hardcodes `STATS_DAYS = 30`, so alerted and snoozed instances are counted over the last 30 days, based on `created_at`. The endpoint itself counts all time if `num_days` is omitted.

ENDPOINT: GET /signals/stats
FUNCTION: get_signal_stats
SCOPED_TO_SIGNAL: no
INSTANCE_WINDOW: 30