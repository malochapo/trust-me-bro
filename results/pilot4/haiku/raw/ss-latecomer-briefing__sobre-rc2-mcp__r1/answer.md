The deciding function is `generate_read_in_summary`. It first looks for a read-in summary event logged within the last 2 minutes. If it finds one with usable details, it returns that summary. If not, or if the stored one fails to parse, it checks for the AI and conversation plugins and generates a new summary. Nothing was changed.

- `generate_read_in_summary` (`src/dispatch/ai/service.py:583`) makes the call. It passes `READ_IN_SUMMARY_CACHE_DURATION` as `max_age_seconds`, separately for incidents and cases.
- `READ_IN_SUMMARY_CACHE_DURATION = 120` (`src/dispatch/ai/constants.py:2`) sets the age limit at 2 minutes.
- `get_recent_summary_event` (`src/dispatch/event/service.py:841`) finds the earlier briefing. It takes the newest event from the `dispatch_genai` source whose description matches the read-in-summary text and whose `started_at` is no older than the cutoff.

FILE: src/dispatch/ai/service.py
FUNCTION: generate_read_in_summary
MAX_AGE: 120 seconds
LOOKUP: get_recent_summary_event