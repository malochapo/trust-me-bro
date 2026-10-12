The briefing is a "read-in summary." `generate_read_in_summary` decides whether to reuse an earlier one or generate a new one. It reuses a summary only if it was written within the last 2 minutes. Otherwise it fetches the conversation, calls the AI plugin, and logs a new summary event.

- **Deciding function:** `generate_read_in_summary` in `src/dispatch/ai/service.py:583`. It checks for a recent summary event at lines 607–615. If one exists and its stored details parse, it returns that summary. If parsing fails, it logs a warning and generates a new one.
- **Maximum age:** `READ_IN_SUMMARY_CACHE_DURATION = 120` in `src/dispatch/ai/constants.py:2`, which is 120 seconds (2 minutes). The value is passed as `max_age_seconds`.
- **Lookup function:** `get_recent_summary_event` in `src/dispatch/event/service.py:841`. It queries the subject's events for the newest one with source `dispatch_genai` and a read-in-summary description, started after `utcnow() - max_age_seconds`. It is called with `incident_id` for incidents and `case_id` for cases.

I didn't change any code. I recorded this as a finding in the sobre session.

FILE: src/dispatch/ai/service.py
FUNCTION: generate_read_in_summary
MAX_AGE: 120 seconds
LOOKUP: get_recent_summary_event