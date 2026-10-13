`generate_read_in_summary` in `src/dispatch/ai/service.py` makes the decision. It first calls `event_service.get_recent_summary_event(...)`. If that returns an event with stored `details`, it rebuilds a `ReadInSummary` from those details and returns it without calling the AI plugin. If there is no such event, or the stored details fail to parse, it generates a new summary.

The age limit is the constant `READ_IN_SUMMARY_CACHE_DURATION = 120` in `src/dispatch/ai/constants.py`, which is 2 minutes. `generate_read_in_summary` passes it as `max_age_seconds`. `get_recent_summary_event` has its own default of 300 seconds, but that default is never used because the caller always passes the constant.

`get_recent_summary_event` (in `src/dispatch/event/service.py`) does the lookup. It returns the newest read-in-summary event for the incident or case, taken from the `dispatch_genai` source, whose `started_at` falls within the age limit.

FILE: src/dispatch/ai/service.py
FUNCTION: generate_read_in_summary
MAX_AGE: 120 seconds (2 minutes)
LOOKUP: get_recent_summary_event