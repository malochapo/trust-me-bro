The reuse decision is made in `generate_read_in_summary`. It hands out a stored briefing if one is less than 2 minutes old, and otherwise generates a new one. The lookup is `get_recent_summary_event`, which finds the newest matching event within that window. I did not change any code.

- `generate_read_in_summary` (`src/dispatch/ai/service.py:583`) first calls the lookup and returns the stored summary if it parses. If there is none, or it fails to parse, it checks the AI and conversation plugins, reads the channel, calls the model, and logs a new event.
- The age limit is `READ_IN_SUMMARY_CACHE_DURATION = 120` in `src/dispatch/ai/constants.py:2`, with the comment "2 minutes".
- `get_recent_summary_event` (`src/dispatch/event/service.py:841`) takes the cutoff as now minus `max_age_seconds`. It filters by incident or case, by the AI source, and by the read-in summary description. It then returns the newest match by `started_at`.

FILE: src/dispatch/ai/service.py
FUNCTION: generate_read_in_summary
MAX_AGE: 120 seconds (2 minutes)
LOOKUP: get_recent_summary_event