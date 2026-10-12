Dispatch reuses an earlier briefing only if it was created within the last 2 minutes. The decision is in `generate_read_in_summary`, and the earlier briefing is found by `get_recent_summary_event`.

- **Deciding function:** `generate_read_in_summary` (`src/dispatch/ai/service.py:583`). It checks for a recent summary event and, if one exists with details that parse, returns it. Otherwise it generates a new summary.
- **Max age:** `READ_IN_SUMMARY_CACHE_DURATION = 120` seconds (2 minutes) in `src/dispatch/ai/constants.py:2`. The caller passes this value explicitly, so it overrides the 300-second default in `get_recent_summary_event`.
- **Lookup:** `get_recent_summary_event` (`src/dispatch/event/service.py:840`). It queries for the latest `Event` on the incident or case with source `dispatch_genai`, a description starting with the read-in-summary text, and `started_at` at or after now minus the max age.

Because the lookup matches on the description prefix and passes an empty `participant_email`, a briefing generated for one participant can be handed to a later participant within those 2 minutes. That matches the behaviour you described.

I didn't change any code, and I didn't run the tests.

FILE: src/dispatch/ai/service.py
FUNCTION: generate_read_in_summary
MAX_AGE: 120 seconds
LOOKUP: get_recent_summary_event