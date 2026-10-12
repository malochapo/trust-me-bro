`generate_read_in_summary` in `src/dispatch/ai/service.py` makes the decision. It first asks `get_recent_summary_event` (in `src/dispatch/event/service.py`) for an earlier read-in summary event on the same incident or case. If that event exists and its stored details parse into a `ReadInSummary`, the function returns the stored summary. Otherwise it logs a warning for a parse failure, or goes straight on, and writes a new summary with the AI plugin.

The age limit is `READ_IN_SUMMARY_CACHE_DURATION`, defined as 120 seconds in `src/dispatch/ai/constants.py`. `generate_read_in_summary` passes it as `max_age_seconds`, so it overrides the lookup's own 300-second default. The lookup only returns events whose `started_at` is within that window and takes the newest one.

FILE: src/dispatch/ai/service.py
FUNCTION: generate_read_in_summary
MAX_AGE: 120 seconds (2 minutes)
LOOKUP: get_recent_summary_event