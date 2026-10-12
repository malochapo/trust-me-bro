The briefing is the read-in summary, and the reuse decision is made in `generate_read_in_summary`. Earlier briefings are reused only if they are two minutes old or less. I did not change any code.

- **Deciding function:** `generate_read_in_summary` (`src/dispatch/ai/service.py:583`). It checks for a recent summary event first. If one exists and its details parse as a `ReadInSummary`, it returns that. Otherwise it generates a new summary. If parsing fails, it logs a warning and generates a new one.
- **Maximum age:** `READ_IN_SUMMARY_CACHE_DURATION = 120` seconds, defined in `src/dispatch/ai/constants.py:2`.
- **Lookup function:** `get_recent_summary_event` (`src/dispatch/event/service.py:841`), called with the subject's incident or case ID and the max age.

FILE: src/dispatch/ai/service.py
FUNCTION: generate_read_in_summary
MAX_AGE: 120 seconds
LOOKUP: get_recent_summary_event