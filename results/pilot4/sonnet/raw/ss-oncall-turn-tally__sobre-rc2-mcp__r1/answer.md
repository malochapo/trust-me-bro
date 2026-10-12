The numbers are worked out in `find_schedule_and_send`, in `src/dispatch/feedback/service/scheduled.py`. It asks the oncall plugin which person just went off shift. It then counts incidents where that person was the commander and cases where they were the assignee, plus the active participants in each. It sends the totals with the feedback message.

**Fallback window:** if the paging tool gives no `shift_start`, the function sets `hours_in_shift = 7 * 24`, so it looks back 7 days. When `shift_start` is given, it uses the length of the shift from `shift_start` to `shift_end`.

**Other projects:** yes. The incident and case lookups are `incident_service.get_all_last_x_hours` and `case_service.get_all_last_x_hours`. Both filter only on `created_at` and take no project argument, so they return records from every project. The function then keeps the ones where the commander's or assignee's email matches the person coming off shift. Incidents they led in other projects are therefore counted. The same applies to cases.

FILE: src/dispatch/feedback/service/scheduled.py
FUNCTION: find_schedule_and_send
FALLBACK_WINDOW: 7 days
OTHER_PROJECTS: yes