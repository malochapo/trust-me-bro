The function is `find_schedule_and_send` in `src/dispatch/feedback/service/scheduled.py`. It counts incidents and cases the outgoing on-call person handled, and includes their active participants in `num_participants`.

When the paging tool gives no shift start, the window is 7 days (168 hours). The code sets `hours_in_shift = 7 * 24` in that case. Otherwise it uses the shift's end minus start.

Incidents they led in other projects are included. `incident_service.get_all_last_x_hours` and `case_service.get_all_last_x_hours` filter only on `created_at` and never on project, and `find_schedule_and_send` does not filter by project either. The count matches on the commander's email for incidents, and on the assignee's email for cases that have a channel.

Two things about the window that you may not expect. It runs back from the current time, not back from the shift's end. And it filters on when each incident or case was created, not when the on-call person handled it.

FILE: src/dispatch/feedback/service/scheduled.py
FUNCTION: find_schedule_and_send
FALLBACK_WINDOW: 7 days
OTHER_PROJECTS: yes