The briefing is the AI "read-in summary," and the decision happens in `generate_read_in_summary`. It reuses a stored summary if one is recent enough, and otherwise calls the AI plugin to write a new one.

- **Decision:** `generate_read_in_summary` in `src/dispatch/ai/service.py:583`. It first looks for a recent summary event for the incident (or case). If that event exists and its details parse as a `ReadInSummary`, it returns that cached summary. If the parse fails, it logs a warning and generates a new one. Otherwise it checks that the AI and conversation plugins are enabled, reads the channel conversation, and calls `chat_parse`. It then logs the result as a new event, so later latecomers can reuse it.
- **Age limit:** `READ_IN_SUMMARY_CACHE_DURATION = 120` in `src/dispatch/ai/constants.py`, which is 2 minutes. This is passed as `max_age_seconds`.
- **Lookup:** `get_recent_summary_event` in `src/dispatch/event/service.py:841`, called as `event_service.get_recent_summary_event`. It finds the earlier summary event for the incident or case.

So when several people join in quick succession, anyone arriving within 2 minutes of a stored summary gets that same briefing again. Anyone arriving after that gets a freshly generated one.

I saved this as a finding in the sobre session. I did not change any code.

FILE: src/dispatch/ai/service.py
FUNCTION: generate_read_in_summary
MAX_AGE: 120 seconds
LOOKUP: get_recent_summary_event