The deciding logic is in `generate_read_in_summary`. It checks for a recent stored summary event before calling the model. If one exists and parses, it returns that briefing; otherwise it generates a new one. The reuse window is 120 seconds (2 minutes), set by `READ_IN_SUMMARY_CACHE_DURATION`. The lookup is `get_recent_summary_event`, which filters `Event` rows by subject, AI source, and the read-in-summary description, and takes the newest one whose `started_at` falls inside the window. That function's own default is 300 seconds, but the caller always passes the 120-second constant, so the default doesn't apply here.

I didn't change any code.

FILE: src/dispatch/ai/service.py
FUNCTION: generate_read_in_summary
MAX_AGE: 120 seconds
LOOKUP: get_recent_summary_event