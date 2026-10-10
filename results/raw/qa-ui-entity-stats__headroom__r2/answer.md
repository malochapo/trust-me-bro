The UI calls `SignalApi.getStats` (`signal/api.js`) from `signal/instance/store.js:130`. That function requests `/signals/stats` with `entity_type_id`, `entity_value` and `num_days`. The route is `return_signal_stats` in `signal/views.py:285`, which calls `get_signal_stats` in `signal/service.py:985`.

**Scope to the signal:** no. The UI never passes a signal id, so `signal_id` is `None` in `get_signal_stats`. The alerted and snoozed instance counts are therefore taken across all signals for that entity. The snooze counts are also not limited to a signal: they match any `SignalFilter` whose expression references the entity.

A separate route, `GET /signals/{signal_id}/stats`, does scope the instance counts to one signal, but the UI doesn't use it.

**Window:** the store sets `STATS_DAYS = 30` and passes it as `num_days`. The alerted and snoozed instance counts only include instances with `created_at` in the last 30 days. The active and expired snooze counts have no date filter.

ENDPOINT: GET /signals/stats
FUNCTION: get_signal_stats
SCOPED_TO_SIGNAL: no
INSTANCE_WINDOW: 30