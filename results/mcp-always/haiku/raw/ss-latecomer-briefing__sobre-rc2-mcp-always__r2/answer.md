The decision is made in `generate_read_in_summary`. It first looks for a recent stored summary event, and if one is younger than the cache window it returns that summary. Otherwise it generates a new one. The reuse check is inline there, not in a separate helper.

The window is 120 seconds, set by `READ_IN_SUMMARY_CACHE_DURATION` in `src/dispatch/ai/constants.py`. The lookup filters `Event.started_at` against `datetime.utcnow() - max_age_seconds`. That lookup is `get_recent_summary_event` in `src/dispatch/event/service.py`, which defaults to 300 seconds but is always called with the 120-second constant.

One thing I noticed while reading: the lookup is not keyed by participant. The call in `generate_read_in_summary` passes no `participant_email`, and the event description is matched only by prefix, so a latecomer can receive a summary generated for a different person within those two minutes. I did not run anything to confirm this in practice.

FILE: src/dispatch/ai/service.py
FUNCTION: generate_read_in_summary
MAX_AGE: 120 seconds
LOOKUP: get_recent_summary_event