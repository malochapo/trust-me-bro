The counting is done in `find_schedule_and_send`, in `src/dispatch/feedback/service/scheduled.py`. I didn't change any code.

- **What it does:** it asks the paging plugin which on-call person just went off shift. It then counts the incidents where that person was the commander, and the cases with a channel where they were the assignee. It also counts active participants in those, and sends the feedback message with the totals.
- **Fallback window:** when the plugin gives no `shift_start`, the window defaults to `7 * 24` hours, which is 7 days. If a start is given, the window is the shift's length (end minus start).
- **Other projects:** yes. The lookups `incident_service.get_all_last_x_hours` and `case_service.get_all_last_x_hours` filter only on `created_at`, with no `project_id` filter. Incidents they led in other projects are therefore included. The same goes for cases. The only check is that the commander's email matches the on-call person's. The `project` argument is used only to look up the individual and send the message.

FILE: src/dispatch/feedback/service/scheduled.py
FUNCTION: find_schedule_and_send
FALLBACK_WINDOW: 7 days (168 hours)
OTHER_PROJECTS: yes