The counts come from `find_schedule_and_send` in `src/dispatch/feedback/service/scheduled.py`. It asks the oncall plugin whether the person just went off shift, then counts their incidents and cases. It sends the questionnaire with those counts.

- **Fallback window:** If the paging tool gives no `shift_start`, the function uses `hours_in_shift = 7 * 24`, which is 7 days (168 hours). When a start is given, it uses the shift length (end minus start) instead.
- **Other projects:** Yes, they are included. The lookups `incident_service.get_all_last_x_hours` and `case_service.get_all_last_x_hours` filter only on `created_at`. Neither filters by project, so the count covers every project the database holds. The loop then keeps only incidents whose commander's email matches the person who went off shift. The same applies to cases, which also have to have a channel and an assignee with that email.

FILE: src/dispatch/feedback/service/scheduled.py
FUNCTION: find_schedule_and_send
FALLBACK_WINDOW: 7 days
OTHER_PROJECTS: yes