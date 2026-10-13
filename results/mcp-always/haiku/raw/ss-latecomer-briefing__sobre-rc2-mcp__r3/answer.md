The decision happens in `generate_read_in_summary`. It checks for a recent AI read-in summary event and, if one is fresh enough and parses, returns it. Otherwise it generates a new summary. The cache window is set in `src/dispatch/ai/constants.py`, and the earlier event is found by `get_recent_summary_event` in `src/dispatch/event/service.py`, which filters on the event's `started_at` against the cutoff.

FILE: src/dispatch/ai/service.py
FUNCTION: generate_read_in_summary
MAX_AGE: 120 seconds
LOOKUP: get_recent_summary_event