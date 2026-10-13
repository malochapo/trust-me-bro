`generate_read_in_summary` decides whether to reuse an earlier briefing or write a new one. It is in `src/dispatch/ai/service.py`, at line 583.

- **Decision:** the function first looks for a recent read-in summary for the same incident or case. If it finds one and can parse the summary stored in that event's `details`, it returns that summary. If parsing fails, it logs a warning and generates a new one. It also generates a new one when no recent summary exists.
- **Age limit:** the function passes `READ_IN_SUMMARY_CACHE_DURATION` as `max_age_seconds`. That constant is 120 seconds, defined in `ai/constants.py`. The lookup function's own default is 300 seconds, but this caller overrides it, so 120 seconds is what applies.
- **Lookup:** `get_recent_summary_event` in `src/dispatch/event/service.py` finds the earlier briefing. It queries for the newest Event from the `dispatch_genai` source, with a read-in-summary-created description, for the same incident or case. It only considers events whose `started_at` is within the age limit.

FILE: src/dispatch/ai/service.py
FUNCTION: generate_read_in_summary
MAX_AGE: 120 seconds
LOOKUP: get_recent_summary_event