The decision is made in `generate_read_in_summary` in `src/dispatch/ai/service.py:583`. It first asks for a recent summary event for the incident or case. If it finds one with stored details, it parses the stored summary and returns it without calling the AI. If nothing is found, or the stored data fails to parse, it generates a new summary.

The age limit comes from `READ_IN_SUMMARY_CACHE_DURATION = 120` in `src/dispatch/ai/constants.py:2`, which is 2 minutes. `generate_read_in_summary` passes it as `max_age_seconds`. The lookup function has its own default of 300 seconds (5 minutes), but that default is not used here.

The lookup is `get_recent_summary_event` in `src/dispatch/event/service.py:841`. It finds the newest AI-generated read-in-summary event for that incident or case whose `started_at` falls within the age window.

FILE: src/dispatch/ai/service.py
FUNCTION: generate_read_in_summary
MAX_AGE: 120 seconds
LOOKUP: get_recent_summary_event