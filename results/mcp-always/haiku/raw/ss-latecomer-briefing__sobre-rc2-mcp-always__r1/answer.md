The deciding function is `generate_read_in_summary`. It checks for a recent cached read-in summary event before it calls the AI plugin, so if a recent one exists it returns that instead of writing a new briefing.

- **Deciding function:** `generate_read_in_summary` (`src/dispatch/ai/service.py:583`). Lines 607–620 check for a recent summary event and return its stored details if they parse. Only if there is no usable event does it go on to build the conversation and call the AI model.
- **Maximum age:** `READ_IN_SUMMARY_CACHE_DURATION = 120` in `src/dispatch/ai/constants.py`, which is 2 minutes. The lookup only matches events whose `started_at` is within that window.
- **Lookup:** `get_recent_summary_event` (`src/dispatch/event/service.py:841`) queries the newest matching AI event for the incident or case.

The cache is keyed on the subject, not on the participant. The lookup filters on the description prefix with `participant_email=''`, so a briefing generated for one latecomer can be returned to the next latecomer who asks within two minutes, even though the event was written for someone else. I did not confirm that from the Slack handler's call path beyond reading the cache logic. I also did not run anything, and I did not change any code.

FILE: src/dispatch/ai/service.py
FUNCTION: generate_read_in_summary
MAX_AGE: 120 seconds
LOOKUP: get_recent_summary_event