`generate_read_in_summary` in `src/dispatch/ai/service.py` makes the decision. It calls `event_service.get_recent_summary_event` first. If that returns an event whose stored details parse as a `ReadInSummary`, it returns that summary and does not call the AI plugin. If nothing is found, or the stored details fail to parse, it writes a new summary.

The age limit is set by `READ_IN_SUMMARY_CACHE_DURATION = 120` in `src/dispatch/ai/constants.py`, so 2 minutes. `generate_read_in_summary` passes this value as `max_age_seconds`. The lookup function's own default is 300 seconds (5 minutes), but that default is not used on this path.

The lookup, `get_recent_summary_event` in `src/dispatch/event/service.py`, finds the newest read-in-summary event for the incident or case. That event must come from the `dispatch_genai` source and have a `started_at` inside the age window.

FILE: src/dispatch/ai/service.py
FUNCTION: generate_read_in_summary
MAX_AGE: 120 seconds
LOOKUP: get_recent_summary_event