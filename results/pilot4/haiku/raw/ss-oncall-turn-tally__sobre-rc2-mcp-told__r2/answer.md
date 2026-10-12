The counts are computed in `find_schedule_and_send`. When the shift start is unknown, the window is 7 days, and incidents led in other projects are included.

- **Function:** `find_schedule_and_send` builds `num_incidents`, `num_cases` and `num_participants` for the person who just went off shift, then sends the questionnaire. It uses `hours_in_shift` as the look-back window.
- **Window:** If the paging tool gives a shift start, `hours_in_shift` is the shift length (end minus start). If not, it defaults to `7 * 24` hours, which is 168 hours. The helpers filter on `created_at >= now - hours`, so the window runs back from the time the job runs, not from the shift end.
- **Other projects:** `incident_service.get_all_last_x_hours` and `case_service.get_all_last_x_hours` do not filter by project. The code matches on commander or assignee email only, so incidents or cases they led in other projects of the same organization are counted. The project-scoped variants (`get_all_last_x_hours_by_status`) are not used here.

I did not change any code. I also saved this finding to the sobre session.

FILE: src/dispatch/feedback/service/scheduled.py
FUNCTION: find_schedule_and_send
FALLBACK_WINDOW: 168 hours
OTHER_PROJECTS: yes