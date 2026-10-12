The deciding function is `generate_read_in_summary`. It checks for a recent summary event first and returns that one if it is fresh enough. Otherwise it calls the model and writes a new summary.

- **Decision:** `generate_read_in_summary` in `src/dispatch/ai/service.py` (around line 583). It calls `get_recent_summary_event` with `max_age_seconds=READ_IN_SUMMARY_CACHE_DURATION`. If an event comes back and its stored details parse as a `ReadInSummary`, it returns that cached summary. If parsing fails, it logs a warning and generates a new one.
- **Maximum age:** `READ_IN_SUMMARY_CACHE_DURATION = 120`, defined in `src/dispatch/ai/constants.py` with the comment "2 minutes". So a briefing up to 120 seconds old is handed out again.
- **Lookup:** `get_recent_summary_event` in `src/dispatch/event/service.py` (around line 840). It finds the most recent AI read-in summary event for the incident or case.

The terminology is "read-in summary" rather than "briefing". I found this with a semantic search and then confirmed it by reading the code. I did not change any code.

I also loaded the sobre session, but there was no earlier saved session for this project, so I did not record findings there.

FILE: src/dispatch/ai/service.py
FUNCTION: generate_read_in_summary
MAX_AGE: 120 seconds
LOOKUP: get_recent_summary_event