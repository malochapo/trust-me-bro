The function is `find_schedule_and_send` in `src/dispatch/feedback/service/scheduled.py`. It asks the oncall plugin whether someone just went off shift, then counts their incidents and cases and sends the feedback message with those numbers.

- **Fallback window:** if the paging tool gives no `shift_start`, it assumes a 7-day shift (`hours_in_shift = 7 * 24`). The counts then cover the last 168 hours.
- **Other projects:** yes, they are included. `incident_service.get_all_last_x_hours` and `case_service.get_all_last_x_hours` filter only on `created_at`, not on `project_id`. The function then keeps incidents whose commander's email matches the oncall person, so incidents they led in other projects of the organization are counted. Cases are handled the same way, except that only cases with a channel and an assignee matching that email are counted.

FILE: src/dispatch/feedback/service/scheduled.py
FUNCTION: find_schedule_and_send
FALLBACK_WINDOW: 7 days (168 hours)
OTHER_PROJECTS: yes