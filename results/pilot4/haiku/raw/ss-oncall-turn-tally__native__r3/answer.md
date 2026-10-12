The function is `find_schedule_and_send`. It runs when a PagerDuty shift has just ended and counts the incidents and cases the outgoing person handled during that turn.

- **Turn length:** it takes the shift start and end from the paging tool and uses their difference as the look-back window. If the paging tool gives no shift start, it falls back to 7 days (168 hours), so the window is measured back from the job's run time.
- **Counting:** an incident counts if the person is its commander. A case counts only if it has a channel and the person is its assignee. Active participants on those are added up as well.
- **Other projects:** included. The incident and case queries (`get_all_last_x_hours`) filter only on creation time, not on project. The schema is per organization (the `tenant` migrations), so incidents they led in other projects of the same organization are counted.

I did not change any code.

FILE: src/dispatch/feedback/service/scheduled.py
FUNCTION: find_schedule_and_send
FALLBACK_WINDOW: 7 days
OTHER_PROJECTS: yes