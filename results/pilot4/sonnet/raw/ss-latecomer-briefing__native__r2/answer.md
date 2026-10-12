`generate_read_in_summary` in `src/dispatch/ai/service.py` decides whether to reuse an earlier briefing or write a new one.

- **How it decides:** It first asks for a recent briefing for the incident or case. If one comes back and its stored details parse as a `ReadInSummary`, it returns that. If none is found, or the stored one fails to parse, it goes on to generate a new one.
- **Age limit:** It passes `max_age_seconds=READ_IN_SUMMARY_CACHE_DURATION` to the lookup. That constant is 120 seconds (2 minutes), set in `src/dispatch/ai/constants.py`. The lookup function's own default is 300 seconds, but the caller always overrides it.
- **Lookup:** `get_recent_summary_event` in `src/dispatch/event/service.py` finds the earlier briefing. It returns the newest AI read-in-summary event for that incident or case whose `started_at` falls within the age limit.

FILE: src/dispatch/ai/service.py
FUNCTION: generate_read_in_summary
MAX_AGE: 120 seconds
LOOKUP: get_recent_summary_event