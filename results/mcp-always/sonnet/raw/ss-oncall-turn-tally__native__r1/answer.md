The counts come from `find_schedule_and_send` in `src/dispatch/feedback/service/scheduled.py`. I didn't change any code.

- **What it does:** it asks the oncall plugin which person just went off shift (`did_oncall_just_go_off_shift`). It then counts incidents where that person was commander and cases where they were assignee, and only cases that have a channel. It also sums the participants who have an active role in each. The totals go into the feedback message, which `send_oncall_shift_feedback_message` sends.
- **Fallback window:** the lookback equals the shift length, worked out from the shift start and end times. If the plugin gives no `shift_start`, it uses `hours_in_shift = 7 * 24`, which is 7 days (168 hours).
- **Other projects:** yes. The lookups `incident_service.get_all_last_x_hours` and `case_service.get_all_last_x_hours` take no project filter. They return every incident or case in the database created within the window. The code then keeps only those whose commander or assignee has the on-call person's email. That email match is not limited to the current project, so incidents they led in other projects are counted. The same applies to cases. I checked only the project filtering, not tenants.

FILE: src/dispatch/feedback/service/scheduled.py
FUNCTION: find_schedule_and_send
FALLBACK_WINDOW: 7 days
OTHER_PROJECTS: yes