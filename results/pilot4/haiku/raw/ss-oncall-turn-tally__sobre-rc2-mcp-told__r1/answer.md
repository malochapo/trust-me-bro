The function is `find_schedule_and_send`. It builds the counts and the questionnaire details for the person whose shift just ended.

When the paging tool gives no shift start, it looks back 7 days (168 hours). When the start is known, the window is the shift length, `shift_end - shift_start`, in hours.

Incidents they led in other projects are counted. The incident and case queries it calls, `get_all_last_x_hours`, filter only on creation time and not on project. The commander-email check then picks up any incident led by that person in any project. Cases are matched on assignee, but only those with a channel, and they are not project-scoped either.

I did not change any code. I saved this as a finding in the sobre session.

FILE: src/dispatch/feedback/service/scheduled.py
FUNCTION: find_schedule_and_send
FALLBACK_WINDOW: 168 hours (7 days)
OTHER_PROJECTS: yes