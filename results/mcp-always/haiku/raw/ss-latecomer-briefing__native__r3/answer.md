The decision is made in `generate_read_in_summary`. It first calls `get_recent_summary_event` and returns the stored briefing if one exists. Otherwise it checks that the AI and conversation plugins are enabled, reads the channel, calls the model, and logs the result as a new event. Only a summary created within the last 2 minutes is reused, because the cutoff is `READ_IN_SUMMARY_CACHE_DURATION = 120` in `src/dispatch/ai/constants.py`. The lookup filters on the subject's `dispatch_genai` read-in-summary events whose `started_at` is at or after `utcnow() - 120s`, and returns the newest one. The function's own default of 300 seconds is not used on this path.

FILE: src/dispatch/ai/service.py
FUNCTION: generate_read_in_summary
MAX_AGE: 120 seconds
LOOKUP: get_recent_summary_event