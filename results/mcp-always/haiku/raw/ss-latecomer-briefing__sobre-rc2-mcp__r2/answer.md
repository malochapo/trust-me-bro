The decision is made in `generate_read_in_summary`. It first looks for a stored read-in summary event newer than the cache window. If it finds one whose details parse, it returns that summary. Otherwise it generates a new one from the channel conversation and records it as an event, which is what later requests can reuse.

The window is set by `READ_IN_SUMMARY_CACHE_DURATION = 120`, in seconds (2 minutes), in `src/dispatch/ai/constants.py`. The lookup function, `get_recent_summary_event` in `src/dispatch/event/service.py`, has a default of 300 seconds, but the caller passes the 120-second constant, so the default does not apply here. The lookup matches events for the incident or case, with `dispatch_genai` as the source and the read-in-summary description, and compares `started_at` against the current UTC time minus the window. It returns the newest match.

FILE: src/dispatch/ai/service.py
FUNCTION: generate_read_in_summary
MAX_AGE: 120 seconds
LOOKUP: get_recent_summary_event