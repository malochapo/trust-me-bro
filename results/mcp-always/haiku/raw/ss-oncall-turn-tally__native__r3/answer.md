The function is `find_schedule_and_send` in `src/dispatch/feedback/service/scheduled.py`. It counts incidents and cases for the person whose shift just ended and passes the totals to the shift-feedback message.

- **Window:** The counts use `hours_in_shift`, computed from the shift's start and end times. The window is applied to each incident's or case's `created_at`, not to the time they were active. If the paging tool gives no shift start, the code falls back to 7 days (168 hours). In the PagerDuty path, `oncall_shift_check` always sets a shift start, so the fallback only applies to other oncall plugins that return no start.
- **Other projects:** Yes. The incident and case queries (`get_all_last_x_hours` in `src/dispatch/incident/service.py` and `src/dispatch/case/service.py`) take no project filter. Incidents are matched by commander email and cases by assignee email, with `has_channel` required for cases. So incidents they led in other projects in the window are counted. The person is looked up within one project, but the counts are not limited to it.

FILE: src/dispatch/feedback/service/scheduled.py
FUNCTION: find_schedule_and_send
FALLBACK_WINDOW: 168 hours (7 days)
OTHER_PROJECTS: yes