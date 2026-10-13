The function is `find_schedule_and_send` in `src/dispatch/feedback/service/scheduled.py`. It counts the incidents and cases for the outgoing on-call person, using the shift length from the paging tool as the lookback window.

- **Turn start unknown:** if the paging tool returns no shift start, the function falls back to 7 days (168 hours) (`scheduled.py`, the `else` branch that sets `hours_in_shift = 7 * 24`).
- **Other projects:** yes. The lookback helpers `incident_service.get_all_last_x_hours` and `case_service.get_all_last_x_hours` take no project filter, so they return incidents and cases from every project. The function then keeps only those whose commander or assignee email matches the on-call person. Only the individual lookup is scoped to the project.

Two details you might not expect. The window is measured back from when the feedback is sent, using `created_at`, not from the start of the shift. Cases are counted only if they have a channel (`case.has_channel`).

I didn't change any code.

FILE: src/dispatch/feedback/service/scheduled.py
FUNCTION: find_schedule_and_send
FALLBACK_WINDOW: 168 hours (7 days)
OTHER_PROJECTS: yes