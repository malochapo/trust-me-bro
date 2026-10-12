The counting happens in `find_schedule_and_send`, in `src/dispatch/feedback/service/scheduled.py`.

- **Which function:** `find_schedule_and_send` asks the paging tool (PagerDuty) whether the on-call person just went off shift. It then counts the incidents they commanded and the cases they were assigned during the shift. Those counts, along with a participant count, go into the feedback message.
- **Fallback window:** If the paging tool gives no `shift_start`, it sets `hours_in_shift = 7 * 24`. That is 7 days, or 168 hours.
- **Other projects:** Yes, they are included. The lookups are `incident_service.get_all_last_x_hours` and `case_service.get_all_last_x_hours`. Both filter only on `created_at` and have no project filter. The loop then matches the commander's or assignee's email against the on-call person's email. Incidents they led in other projects of the same organization therefore count. Cases are counted only if they have a channel (`case.has_channel`).

FILE: src/dispatch/feedback/service/scheduled.py
FUNCTION: find_schedule_and_send
FALLBACK_WINDOW: 7 days
OTHER_PROJECTS: yes