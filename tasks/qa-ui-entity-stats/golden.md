signal/instance/store.js calls SignalApi.getStats(entity_type_id, entity_value), which requests /signals/stats without a signal id; the backend computes it in get_signal_stats.

ENDPOINT: GET /signals/stats
FUNCTION: get_signal_stats
SCOPED_TO_SIGNAL: no
