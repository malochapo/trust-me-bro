`generate_read_in_summary` in `src/dispatch/ai/service.py` decides between reusing an earlier briefing and writing a new one.

- **How it decides:** It first asks `event_service.get_recent_summary_event` for a recent read-in summary event for the incident or case. If an event comes back and its stored details parse into a summary, it returns that summary. If nothing comes back, or the parse fails (it logs a warning), it generates a fresh summary.
- **How old a briefing may be:** The call passes `max_age_seconds=READ_IN_SUMMARY_CACHE_DURATION`. That constant is 120 seconds, set in `src/dispatch/ai/constants.py`. The lookup function's own default is 300 seconds, but the caller overrides it.
- **How the earlier briefing is found:** `get_recent_summary_event`, in `src/dispatch/event/service.py`, queries the newest GenAI-sourced "read-in summary created" event for that incident or case. It only accepts events whose start time is within the cutoff.

FILE: src/dispatch/ai/service.py
FUNCTION: generate_read_in_summary
MAX_AGE: 120 seconds
LOOKUP: get_recent_summary_event