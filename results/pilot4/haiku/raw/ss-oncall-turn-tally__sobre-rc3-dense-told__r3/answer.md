The function is `find_schedule_and_send` in `src/dispatch/feedback/service/scheduled.py`. It counts incidents and cases for the outgoing on-call person and passes the totals to `send_oncall_shift_feedback_message`.

- **Start of turn:** The paging tool (PagerDuty, via `oncall_shift_check` in `src/dispatch/plugins/dispatch_pagerduty/service.py`) works out the shift start by stepping back 24 hours at a time until the on-call person changes. When it can't determine a start, `shift_start` is `None`.
- **Fallback window:** When the start is unknown, `hours_in_shift = 7 * 24`, so the window is **168 hours (7 days)**.
- **Other projects:** Incidents are matched on `incident.commander.individual.email`, and cases on `case.assignee.individual.email` with `case.has_channel`. Neither count is restricted by `project_id`. The lookups go through `incident_service.get_all_last_x_hours` and `case_service.get_all_last_x_hours`, which take only `db_session` and `hours`. So incidents they led in other projects of the same organization are included.

FILE: src/dispatch/feedback/service/scheduled.py
FUNCTION: find_schedule_and_send
FALLBACK_WINDOW: 168 hours (7 days)
OTHER_PROJECTS: yes