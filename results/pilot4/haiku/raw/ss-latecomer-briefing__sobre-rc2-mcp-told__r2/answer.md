The briefing is called a "read-in summary" in the code. The decision is made in `generate_read_in_summary`, which first looks for a recent summary event and reuses its stored details if one exists. Otherwise it generates a new one. I did not change any code.

- **Deciding function:** `generate_read_in_summary` (`src/dispatch/ai/service.py:583`). It calls `event_service.get_recent_summary_event` and returns the stored summary if one is found and parses. Otherwise it generates a new one.
- **Maximum age:** `get_recent_summary_event` has a default `max_age_seconds` of 300 (5 minutes), but the caller passes `READ_IN_SUMMARY_CACHE_DURATION`, which is defined as 120 seconds in `src/dispatch/ai/constants.py:2`. So a briefing up to 2 minutes old is handed out again. The test at `tests/ai/test_ai_service.py:430` asserts this value.
- **Lookup function:** `get_recent_summary_event` (`src/dispatch/event/service.py:841`). It queries for the latest `dispatch_genai` event whose description starts with the read-in summary prefix, for the incident or case, with `started_at` within the cutoff.

I also saved this as a finding in sobre.

FILE: src/dispatch/ai/service.py
FUNCTION: generate_read_in_summary
MAX_AGE: 120 seconds
LOOKUP: get_recent_summary_event