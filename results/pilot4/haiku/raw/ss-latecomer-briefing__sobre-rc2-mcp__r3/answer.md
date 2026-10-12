The reuse decision lives in `generate_read_in_summary`. It checks for a stored read-in summary event no older than 120 seconds and returns that one if it parses; otherwise it generates a new briefing. The earlier briefing is found by `get_recent_summary_event`. I didn't change any code.

- **Deciding function:** `generate_read_in_summary` in `src/dispatch/ai/service.py` (around line 583). It calls `get_recent_summary_event` with `max_age_seconds=READ_IN_SUMMARY_CACHE_DURATION`, and if a recent event with details parses into a `ReadInSummary`, it returns that. If parsing fails, it logs a warning and generates a new summary.
- **Max age:** `READ_IN_SUMMARY_CACHE_DURATION = 120` in `src/dispatch/ai/constants.py`, so 120 seconds (2 minutes).
- **Lookup:** `get_recent_summary_event` in `src/dispatch/event/service.py` (around line 841). It queries for the newest `Event` on the incident or case with the `dispatch_genai` source and the read-in-summary-created description, with `started_at` at or after now minus `max_age_seconds`.

Note that the lookup's own default is 300 seconds, but the briefing path always passes the 120-second constant, so the 120-second value is the one that applies.

FILE: src/dispatch/ai/service.py
FUNCTION: generate_read_in_summary
MAX_AGE: 120 seconds
LOOKUP: get_recent_summary_event