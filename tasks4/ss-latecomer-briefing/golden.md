generate_read_in_summary first calls event_service.get_recent_summary_event with max_age_seconds=READ_IN_SUMMARY_CACHE_DURATION (120, in dispatch/ai/constants.py); a matching AI event in the incident's or case's event log is parsed back into a ReadInSummary and returned instead of calling the model again.

FILE: src/dispatch/ai/service.py
FUNCTION: generate_read_in_summary
MAX_AGE: 120 seconds
LOOKUP: get_recent_summary_event
