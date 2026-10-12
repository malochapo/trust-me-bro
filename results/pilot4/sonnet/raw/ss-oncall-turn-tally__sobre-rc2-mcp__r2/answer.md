The function is `find_schedule_and_send` in `src/dispatch/feedback/service/scheduled.py`. It runs once the oncall plugin reports that someone just went off shift. It counts the incidents they commanded and the cases they were assigned, plus the active participants on both. It then sends the feedback message with those numbers.

- **Fallback window:** If the paging tool gives no `shift_start`, the function sets `hours_in_shift = 7 * 24`, so it looks back 7 days (168 hours). When the start is known, the window is `shift_end - shift_start`.
- **Other projects:** Yes, they are included. `incident_service.get_all_last_x_hours` and `case_service.get_all_last_x_hours` only filter on `created_at` and take no project filter. The function then matches on the commander's email (or the case assignee's email), so incidents they led in any project count. The same applies to cases, but only those that have a channel (`case.has_channel`).

I didn't change any code.

FILE: src/dispatch/feedback/service/scheduled.py
FUNCTION: find_schedule_and_send
FALLBACK_WINDOW: 7 days
OTHER_PROJECTS: yes