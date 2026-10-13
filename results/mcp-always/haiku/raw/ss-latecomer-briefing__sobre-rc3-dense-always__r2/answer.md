The deciding function is `generate_read_in_summary` in `src/dispatch/ai/service.py`. At its top it looks for a recent read-in summary event. If one exists and parses, it returns that cached summary. Otherwise it goes on to generate a new one. The lookup uses `READ_IN_SUMMARY_CACHE_DURATION`, which is defined as 120 seconds in `src/dispatch/ai/constants.py:2`. The earlier lookup function is `get_recent_summary_event` in `src/dispatch/event/service.py`, which queries for a summary event newer than that cutoff.

I only read the code and changed nothing. The `max_age_seconds` default of 300 in `get_recent_summary_event` is not what the latecomer path uses, because `generate_read_in_summary` always passes the 120-second constant.

FILE: src/dispatch/ai/service.py
FUNCTION: generate_read_in_summary
MAX_AGE: 120 seconds
LOOKUP: get_recent_summary_event