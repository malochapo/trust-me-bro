The deciding function is `generate_read_in_summary`. It reuses an earlier briefing if one was created within the last 120 seconds, and otherwise generates a new one. The lookup is `get_recent_summary_event`.

- **Reuse check:** `generate_read_in_summary` (`src/dispatch/ai/service.py:583`) first looks for a recent read-in summary event for the incident or case. If one exists and its details parse as a `ReadInSummary`, it returns that cached summary without calling the model. If parsing fails, it logs a warning and generates a new one.
- **Maximum age:** `READ_IN_SUMMARY_CACHE_DURATION = 120  # 2 minutes` (`src/dispatch/ai/constants.py:2`).
- **Lookup:** `get_recent_summary_event` (`src/dispatch/event/service.py:841`) filters events by incident or case ID, the `dispatch_genai` source, and the read-in summary description. It also requires `started_at` to be within the cutoff, and returns the newest match.

I made no code changes. I recorded the finding in the sobre session.

FILE: src/dispatch/ai/service.py
FUNCTION: generate_read_in_summary
MAX_AGE: 120 seconds
LOOKUP: get_recent_summary_event