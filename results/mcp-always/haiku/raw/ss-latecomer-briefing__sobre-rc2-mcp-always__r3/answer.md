The deciding function is `generate_read_in_summary`. It checks for a recent cached summary event first and reuses it if one exists. Otherwise it calls the AI plugin for a new briefing.

- **Cache window:** `READ_IN_SUMMARY_CACHE_DURATION = 120` in `src/dispatch/ai/constants.py:2`, which is 2 minutes. The cache check runs before any AI or conversation plugin lookup.
- **Lookup:** `get_recent_summary_event` in `src/dispatch/event/service.py` returns the newest `dispatch_genai` event for the incident whose description starts with the read-in-summary text and whose `started_at` falls within the window.

FILE: src/dispatch/ai/service.py
FUNCTION: generate_read_in_summary
MAX_AGE: 120 seconds
LOOKUP: get_recent_summary_event