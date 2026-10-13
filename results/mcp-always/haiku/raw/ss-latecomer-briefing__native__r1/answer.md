The reuse decision lives in `generate_read_in_summary`. It checks for a recent cached summary event first, and only builds a new briefing if none is found or the cached one fails to parse. The cache window is set by `READ_IN_SUMMARY_CACHE_DURATION = 120  # 2 minutes` in `src/dispatch/ai/constants.py`, and the lookup is `get_recent_summary_event` in `src/dispatch/event/service.py`, which filters on `started_at` against that window.

FILE: src/dispatch/ai/service.py
FUNCTION: generate_read_in_summary
MAX_AGE: 120 seconds (2 minutes)
LOOKUP: get_recent_summary_event