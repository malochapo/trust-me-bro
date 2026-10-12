`generate_read_in_summary` in `src/dispatch/ai/service.py` makes the decision. It first asks `get_recent_summary_event` (in `src/dispatch/event/service.py`) for a recent read-in summary event for the incident or case. If that event exists and its stored details parse as a `ReadInSummary`, the function returns that summary. Otherwise it generates a new one. A parse failure only logs a warning and falls through to generating a fresh summary.

The age limit is `READ_IN_SUMMARY_CACHE_DURATION`, defined in `src/dispatch/ai/constants.py` as 120 seconds (2 minutes). It is passed to the lookup as `max_age_seconds`.

The lookup function has its own default of 300 seconds, but the caller always overrides it with the 120-second constant, so 120 seconds is what applies.

The lookup filters events by incident or case ID and by the `dispatch_genai` source. It also requires the "read-in summary created" description prefix and a start time inside the age window. It returns the newest match.

FILE: src/dispatch/ai/service.py
FUNCTION: generate_read_in_summary
MAX_AGE: 120 seconds
LOOKUP: get_recent_summary_event