The decision is made in `generate_read_in_summary`, which reuses an earlier read-in summary if one is recent enough and otherwise generates a new one. A reused briefing can be up to 120 seconds old (`READ_IN_SUMMARY_CACHE_DURATION = 120  # 2 minutes` in `src/dispatch/ai/constants.py`). The lookup is `get_recent_summary_event` in `src/dispatch/event/service.py`, which returns the newest matching AI summary event whose `started_at` falls inside that window. If it finds one with parseable details, the cached summary is returned. Otherwise a new summary is generated.

The function's own default `max_age_seconds` is 300 seconds, but the caller always passes the 120-second constant, so 120 seconds is the effective limit. I made no code changes.

FILE: src/dispatch/ai/service.py
FUNCTION: generate_read_in_summary
MAX_AGE: 120 seconds
LOOKUP: get_recent_summary_event