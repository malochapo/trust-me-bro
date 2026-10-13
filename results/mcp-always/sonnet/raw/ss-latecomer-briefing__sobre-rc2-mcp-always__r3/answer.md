`generate_read_in_summary` in `src/dispatch/ai/service.py` (line 583) makes the decision. It looks for a recent summary first. If it finds one with stored details, it parses that and returns it without calling the AI. If the stored summary fails to parse, it logs a warning and writes a new one. The same happens if there is no recent summary.

**Age limit:** the cutoff comes from `READ_IN_SUMMARY_CACHE_DURATION`, which `src/dispatch/ai/constants.py` sets to 120 seconds (2 minutes). The lookup keeps only events whose `started_at` is at or after now minus that many seconds. Its own default of 300 seconds is not used here, because the caller always passes the 120-second value.

**Lookup:** `get_recent_summary_event` in `src/dispatch/event/service.py` (line 841) finds the earlier briefing. It queries for the newest matching event for the incident or case. The event must come from the `dispatch_genai` source and have a "read-in summary created" description.

FILE: src/dispatch/ai/service.py
FUNCTION: generate_read_in_summary
MAX_AGE: 120 seconds
LOOKUP: get_recent_summary_event