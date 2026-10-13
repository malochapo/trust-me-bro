**Answer:** The function is `find_schedule_and_send` in `src/dispatch/feedback/service/scheduled.py`. It counts incidents and cases for the outgoing on-call person and passes the totals to `send_oncall_shift_feedback_message`.

- **How the turn start is found:** `oncall_shift_check` in `src/dispatch/plugins/dispatch_pagerduty/service.py:184` compares who was on call 18 hours before the hour check with who is on call 2 hours after. If the person changes, it steps back in 24-hour increments until it finds the change, and records that as `shift_start`.
- **Fallback window:** If `shift_start` is missing, `hours_in_shift` is `7 * 24`, so the window is **168 hours (7 days)**. Otherwise the window is `shift_end − shift_start`, in hours.
- **Other projects:** Included. `incident_service.get_all_last_x_hours` and `case_service.get_all_last_x_hours` filter only on `created_at`, with no project or organization filter. Incidents are matched by `incident.commander.individual.email` and cases by `case.assignee.individual.email` (cases also need `has_channel`). So an incident the person led in any project counts.

FILE: src/dispatch/feedback/service/scheduled.py
FUNCTION: find_schedule_and_send
FALLBACK_WINDOW: 168 hours
OTHER_PROJECTS: yes