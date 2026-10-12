`generate_read_in_summary` in `src/dispatch/ai/service.py` decides between reusing and writing. It first asks `event_service.get_recent_summary_event` for a cached briefing. If one comes back and its stored details parse as a `ReadInSummary`, it returns that. Otherwise it goes on to generate a new one.

The age limit is `READ_IN_SUMMARY_CACHE_DURATION`, defined in `src/dispatch/ai/constants.py` as 120 seconds (2 minutes). `generate_read_in_summary` passes it as `max_age_seconds`. `get_recent_summary_event` only accepts events whose `started_at` is within that window. Its own default is 300 seconds, but that default is not used here.

`get_recent_summary_event` is in `src/dispatch/event/service.py`. It queries `Event` rows for the incident or case. They must come from the `dispatch_genai` source and have a "read-in summary created" description. It returns the newest one.

FILE: src/dispatch/ai/service.py
FUNCTION: generate_read_in_summary
MAX_AGE: 120 seconds (2 minutes)
LOOKUP: get_recent_summary_event