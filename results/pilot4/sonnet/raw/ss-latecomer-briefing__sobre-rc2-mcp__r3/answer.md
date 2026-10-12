I've traced it through the code and have what I need.

`generate_read_in_summary` in `src/dispatch/ai/service.py` makes the decision. Before it calls the AI plugin, it looks for a recent read-in summary event for the same incident or case. If one exists and its stored details parse as a `ReadInSummary`, it returns that summary. If none exists, or the parse fails (it logs a warning), it generates a new summary.

The age limit is `READ_IN_SUMMARY_CACHE_DURATION`, defined in `src/dispatch/ai/constants.py` as 120 seconds (2 minutes). `generate_read_in_summary` passes it as `max_age_seconds`.

`get_recent_summary_event` in `src/dispatch/event/service.py` finds the earlier briefing. It returns the newest event with these properties:
- **Subject:** it belongs to the same incident or case.
- **Source:** it comes from the `dispatch_genai` source.
- **Description:** it is a "read-in summary created" event.
- **Age:** it started within the cutoff window.

Its own default is 300 seconds, but the caller overrides that with the 120-second constant.

FILE: src/dispatch/ai/service.py
FUNCTION: generate_read_in_summary
MAX_AGE: 120 seconds
LOOKUP: get_recent_summary_event