The function is `find_schedule_and_send`. It counts incidents where the on-call person is commander and cases where they are assignee (with a channel). When the paging tool gives no shift start, the window is 7 days (168 hours). Incidents and cases led in other projects are included, because the lookup queries don't filter by project.

Details from `src/dispatch/feedback/service/scheduled.py`:

- **Turn start known:** the window is the shift length, computed from the shift start and end times. It is counted back from the current time (`datetime.utcnow()`), not from the shift start.
- **Turn start unknown:** `hours_in_shift = 7 * 24`, the "default to 7 days" branch.
- **Other projects:** `incident_service.get_all_last_x_hours` and `case_service.get_all_last_x_hours` filter only on `created_at`, with no `project_id` filter. The commander and assignee checks compare email only. So an on-call person's incidents and cases in any project of the database are counted.

I did not run this code or check the PagerDuty `oncall_shift_check` to confirm when it returns no shift start. I only read the code and changed nothing.

FILE: src/dispatch/feedback/service/scheduled.py
FUNCTION: find_schedule_and_send
FALLBACK_WINDOW: 168 hours
OTHER_PROJECTS: yes