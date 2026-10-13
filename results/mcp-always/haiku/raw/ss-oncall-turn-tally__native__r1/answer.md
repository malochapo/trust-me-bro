The function is `find_schedule_and_send`, in `src/dispatch/feedback/service/scheduled.py`. It is called from `oncall_shift_feedback`, which runs from the scheduled `oncall-shift-feedback-ucan` and `oncall-shift-feedback-emea` jobs.

- **Counts:** it counts incidents where the outgoing on-call person is the commander, and cases that have a channel and where they are the assignee. It also sums active participants for each.
- **Window:** the window is the shift length, taken from the schedule's shift start and end. If the paging tool gives no shift start, it falls back to `7 * 24` hours (7 days). That window is applied by `created_at` through `incident_service.get_all_last_x_hours` and `case_service.get_all_last_x_hours`.
- **Other projects:** the incident and case queries filter only on `created_at`, not `project_id`. The on-call person is matched by email. So incidents they commanded in other projects of the same organization are included. The shift-end message is sent using the current project, but the counts are not limited to it.

I didn't change any code.

FILE: src/dispatch/feedback/service/scheduled.py
FUNCTION: find_schedule_and_send
FALLBACK_WINDOW: 168 hours
OTHER_PROJECTS: yes