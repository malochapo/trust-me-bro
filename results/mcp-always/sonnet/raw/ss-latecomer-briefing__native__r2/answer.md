The decision is made in `generate_read_in_summary` in `src/dispatch/ai/service.py`.

- **Deciding:** It looks for a recent read-in summary event for the incident or case. If it finds one with stored details, it parses those details and returns them as the summary. If nothing usable turns up, or the stored summary fails to parse, it writes a new one.
- **Age limit:** It passes `max_age_seconds=READ_IN_SUMMARY_CACHE_DURATION` to the lookup. That constant is 120 seconds, set in `src/dispatch/ai/constants.py`.
- **Lookup:** `get_recent_summary_event` in `src/dispatch/event/service.py` does the search. It filters for events from the `dispatch_genai` source whose description marks a created read-in summary. It keeps only those started within the cutoff and returns the newest.
- **Default:** `get_recent_summary_event` has its own default of 300 seconds. That default is never used here, because the caller always passes 120.

FILE: src/dispatch/ai/service.py
FUNCTION: generate_read_in_summary
MAX_AGE: 120 seconds
LOOKUP: get_recent_summary_event