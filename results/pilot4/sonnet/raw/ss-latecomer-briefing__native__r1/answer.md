The deciding function is `generate_read_in_summary` in `src/dispatch/ai/service.py`. It first asks for a recent summary event for the incident or case. If it finds one with stored details, it parses those details and returns that briefing instead of writing a new one. If the stored briefing can't be parsed, it logs a warning and writes a fresh one.

The age limit is `READ_IN_SUMMARY_CACHE_DURATION`, defined in `src/dispatch/ai/constants.py` as 120 seconds (2 minutes). It is passed to the lookup as `max_age_seconds`. The lookup's own default is 300 seconds, but this caller overrides it.

The lookup is `get_recent_summary_event` in `src/dispatch/event/service.py`, called as `event_service.get_recent_summary_event`. It computes a cutoff time of now minus `max_age_seconds` and looks for a summary event newer than that.

FILE: src/dispatch/ai/service.py
FUNCTION: generate_read_in_summary
MAX_AGE: 120 seconds
LOOKUP: get_recent_summary_event