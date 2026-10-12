The numbers are worked out inside `find_schedule_and_send`, in `src/dispatch/feedback/service/scheduled.py`. It counts incidents, cases and participants, then passes them to `send_oncall_shift_feedback_message`. I read the code only and ran nothing.

- **Fallback window:** if the paging tool's `shift_start` is empty, `hours_in_shift` defaults to `7 * 24`, which is 7 days (168 hours). Otherwise the window is the shift length, from `shift_start` to `shift_end`.
- **Other projects:** yes. The lookup functions `incident_service.get_all_last_x_hours` and `case_service.get_all_last_x_hours` take no project ID. They return every incident or case created in the window, across all projects. The loop then filters only by the commander's email for incidents. For cases it filters by the assignee's email and requires `has_channel`. The `project` argument is not used to filter the counts.

FILE: src/dispatch/feedback/service/scheduled.py
FUNCTION: find_schedule_and_send
FALLBACK_WINDOW: 7 days
OTHER_PROJECTS: yes