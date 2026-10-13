The reuse decision is made in `generate_read_in_summary`. It returns a stored summary if one exists within the cache window, and otherwise calls the AI plugin for a new one. The window is `READ_IN_SUMMARY_CACHE_DURATION`, which is set to 120 seconds (2 minutes) in `src/dispatch/ai/constants.py`. The lookup is `get_recent_summary_event` in `src/dispatch/event/service.py`. It filters `Event` rows by incident or case, source `dispatch_genai`, the read-in-summary description, and `started_at` no older than the cutoff, then takes the newest. I read both functions but did not run anything, and I changed no code.

FILE: src/dispatch/ai/service.py
FUNCTION: generate_read_in_summary
MAX_AGE: 120 seconds
LOOKUP: get_recent_summary_event