The decision is made in `generate_read_in_summary`. It looks for a read-in summary event from the last 2 minutes. If it finds one whose details parse, it returns that summary. Otherwise it generates a new one through the AI and conversation plugins. The lookup is `get_recent_summary_event`, which filters `Event` rows by subject, AI source, description prefix, and `started_at` within the cutoff, then takes the newest. The 120-second value is `READ_IN_SUMMARY_CACHE_DURATION` in `src/dispatch/ai/constants.py`. I did not change any code.

- `src/dispatch/ai/service.py:583` decides whether to reuse or regenerate (`generate_read_in_summary`, cache check at lines 607–624).
- `src/dispatch/event/service.py:841` finds the earlier briefing (`get_recent_summary_event`, cutoff at line 849).
- `src/dispatch/ai/constants.py:2` sets the age limit (`READ_IN_SUMMARY_CACHE_DURATION = 120  # 2 minutes`).

FILE: src/dispatch/ai/service.py
FUNCTION: generate_read_in_summary
MAX_AGE: 120 seconds
LOOKUP: get_recent_summary_event