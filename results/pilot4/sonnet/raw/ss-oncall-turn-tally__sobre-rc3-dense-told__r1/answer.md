The counts come from `find_schedule_and_send` in `src/dispatch/feedback/service/scheduled.py`. It asks the paging tool (PagerDuty) who just went off shift. It then counts the incidents they commanded and the cases they were assigned, and sends the feedback message with those numbers.

- **Window:** if `shift_start` is missing, `hours_in_shift` defaults to `7 * 24`, which is 7 days. When the start is known, the window is `shift_end - shift_start`.
- **Other projects:** yes. `incident_service.get_all_last_x_hours` filters only on `created_at` and has no project filter. The loop then keeps incidents whose commander's email matches the on-call person, so incidents they led in any project of the organization are counted.
- **Cases:** the same applies to cases. `case_service.get_all_last_x_hours` is called the same way, and only cases with a channel and a matching assignee are counted. I didn't open that function, so I'm inferring it has no project filter.

I made no code changes.

FILE: src/dispatch/feedback/service/scheduled.py
FUNCTION: find_schedule_and_send
FALLBACK_WINDOW: 7 days
OTHER_PROJECTS: yes