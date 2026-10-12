The counts come from `find_schedule_and_send` in `src/dispatch/feedback/service/scheduled.py`. I only read the code and changed nothing.

- **What it does:** it asks the paging plugin whether the on-call person just went off shift. It then counts the incidents they commanded and the cases they were assigned. For cases it counts only those that have a channel. It also sums the active participants across those incidents and cases, and passes all three numbers to `send_oncall_shift_feedback_message`.
- **Fallback window:** if the paging tool gives no `shift_start`, `hours_in_shift` defaults to `7 * 24` hours, which is 7 days. When the start is known, the window is the length of the shift, from `shift_start` to `shift_end`.
- **Other projects:** yes. `incident_service.get_all_last_x_hours` and `case_service.get_all_last_x_hours` filter only on `created_at`, with no `project_id` filter. Their sibling functions `get_all_last_x_hours_by_status` do filter by project. The only match is on the commander's or assignee's email. Incidents or cases they led in other projects within the window are therefore counted.
- **Caveat on "organization":** the query has no organization filter either. In a multi-tenant deployment the database session is probably scoped to one organization already, but I didn't confirm that.

FILE: src/dispatch/feedback/service/scheduled.py
FUNCTION: find_schedule_and_send
FALLBACK_WINDOW: 7 days (168 hours)
OTHER_PROJECTS: yes