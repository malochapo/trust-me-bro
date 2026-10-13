The decision is made in `generate_read_in_summary`. It checks for a recent cached summary first and only generates a new one if none is found or the cached one can't be parsed. The cache window is 120 seconds, and the earlier summary is found by `get_recent_summary_event`. I read the code but changed nothing.

- **Deciding function:** `generate_read_in_summary` (`src/dispatch/ai/service.py:583`). It calls `get_recent_summary_event` with `max_age_seconds=READ_IN_SUMMARY_CACHE_DURATION`. If that returns an event with details that parse into `ReadInSummary`, it returns that summary. Otherwise it continues to generate a new one.
- **Maximum age:** `READ_IN_SUMMARY_CACHE_DURATION = 120` in `src/dispatch/ai/constants.py:2`, which is 2 minutes.
- **Lookup:** `get_recent_summary_event` (`src/dispatch/event/service.py:841`). It queries the subject's `dispatch_genai` events whose description matches the read-in summary text and whose `started_at` is no older than `utcnow() - max_age_seconds`. It returns the newest match. Incidents and cases use separate filters.

FILE: src/dispatch/ai/service.py
FUNCTION: generate_read_in_summary
MAX_AGE: 120 seconds
LOOKUP: get_recent_summary_event