`generate_read_in_summary` in `src/dispatch/ai/service.py` makes the decision. It first asks `event_service.get_recent_summary_event` for a recent summary event for the incident or case. If it finds one and the event's stored `details` parse as a `ReadInSummary`, it returns that summary. Otherwise it goes on to generate a new one. That includes the case where the stored details fail to parse, which only logs a warning.

The age limit is `READ_IN_SUMMARY_CACHE_DURATION` in `src/dispatch/ai/constants.py`, set to 120 seconds (2 minutes). `generate_read_in_summary` passes it to the lookup as `max_age_seconds`. The lookup's own default is 300 seconds, but that default isn't used here.

`get_recent_summary_event` in `src/dispatch/event/service.py` does the lookup. It filters by incident or case ID and by `Event.source == AIEventSource.dispatch_genai`. It also requires the description to match the "read-in summary created" text. It keeps only events whose `started_at` is within the age limit and returns the newest one.

FILE: src/dispatch/ai/service.py
FUNCTION: generate_read_in_summary
MAX_AGE: 120 seconds
LOOKUP: get_recent_summary_event