`generate_read_in_summary` in `src/dispatch/ai/service.py` makes the decision. It first asks `get_recent_summary_event` (in `src/dispatch/event/service.py`) for an earlier read-in summary on the same incident or case. If one exists and its stored details parse as a `ReadInSummary`, it returns that. Otherwise it generates a new summary through the AI plugin.

The age limit is the constant `READ_IN_SUMMARY_CACHE_DURATION = 120` in `ai/constants.py`, which is 2 minutes. `generate_read_in_summary` passes it to `get_recent_summary_event` as `max_age_seconds`, overriding that function's own 300-second (5-minute) default.

`get_recent_summary_event` looks for an event from the AI source whose description marks a read-in summary as created, and whose `started_at` is within the cutoff. It returns the newest such event.

FILE: src/dispatch/ai/service.py
FUNCTION: generate_read_in_summary
MAX_AGE: 120 seconds (2 minutes)
LOOKUP: get_recent_summary_event