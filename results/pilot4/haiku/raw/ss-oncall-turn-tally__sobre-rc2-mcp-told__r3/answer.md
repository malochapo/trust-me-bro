The counts are computed by `find_schedule_and_send`, and the questionnaire itself is sent by `oncall_shift_feedback`, which calls it for each service. I made no code changes.

- **Function:** `find_schedule_and_send` (`src/dispatch/feedback/service/scheduled.py:77`). It finds the previous on-call person, counts incidents where they are commander and cases where they are assignee with a channel, and counts active participants in those. The counts are sent in `details`.
- **Fallback window:** If the paging tool gives no shift start, the code uses `7 * 24` hours, so 7 days (line 121). When the start is known, the window is the shift length in hours, measured back from now.
- **Other projects:** Yes. The caller passes `project`, but `incident_service.get_all_last_x_hours` and `case_service.get_all_last_x_hours` filter only on creation time, not on `project_id`. Any incident or case in the database whose commander or assignee matches the person's email is counted, whichever project it belongs to. Dispatch keeps each tenant in its own database, so this covers the whole organization's data in that tenant, but I did not confirm that mapping in code.

FILE: src/dispatch/feedback/service/scheduled.py
FUNCTION: find_schedule_and_send
FALLBACK_WINDOW: 7 days
OTHER_PROJECTS: yes