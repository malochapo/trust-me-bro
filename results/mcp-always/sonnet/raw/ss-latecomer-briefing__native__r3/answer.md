`generate_read_in_summary` in `src/dispatch/ai/service.py` makes the decision. It first asks `event_service.get_recent_summary_event` for an earlier briefing on the same incident or case. If it finds one with stored details, it hands that briefing out again. If the lookup finds nothing, or the stored briefing can't be parsed (it logs a warning), the function writes a new one.

- **Age limit:** the cutoff is `READ_IN_SUMMARY_CACHE_DURATION`, set to 120 seconds (2 minutes) in `src/dispatch/ai/constants.py`. The lookup's own default is 300 seconds, but this caller always passes the 120-second value.
- **How the lookup works:** `get_recent_summary_event` is in `src/dispatch/event/service.py`. It returns the newest event for that incident or case that came from the AI source (`dispatch_genai`), has a read-in-summary description, and has a `started_at` no older than the cutoff.

FILE: src/dispatch/ai/service.py
FUNCTION: generate_read_in_summary
MAX_AGE: 120 seconds
LOOKUP: get_recent_summary_event