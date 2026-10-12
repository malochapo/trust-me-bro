The deciding function is `generate_read_in_summary`. It checks for a recent cached summary before it calls the AI plugin, and it hands that summary back if one exists. Otherwise it generates a new one.

- **Reuse window:** `READ_IN_SUMMARY_CACHE_DURATION = 120` in `src/dispatch/ai/constants.py`, which is 2 minutes. A stored summary is reused only if its event `started_at` is no older than that cutoff.
- **Lookup:** `get_recent_summary_event` in `src/dispatch/event/service.py` queries the newest AI read-in summary event for the incident or case, filtered by that cutoff. It is called from `generate_read_in_summary` in `src/dispatch/ai/service.py`.

I only read the code and changed nothing.

FILE: src/dispatch/ai/service.py
FUNCTION: generate_read_in_summary
MAX_AGE: 120 seconds
LOOKUP: get_recent_summary_event