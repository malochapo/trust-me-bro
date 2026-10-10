signal/instance/store.js calls SignalApi.getStats(entity_type_id, entity_value, STATS_DAYS) with STATS_DAYS = 30, which requests /signals/stats?...&num_days=30 without a signal id; the backend computes it in get_signal_stats, where num_days limits the instance counts.

ENDPOINT: GET /signals/stats
FUNCTION: get_signal_stats
SCOPED_TO_SIGNAL: no
INSTANCE_WINDOW: 30 days
