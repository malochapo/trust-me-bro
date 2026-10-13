The numbers are worked out in `find_schedule_and_send`, in `src/dispatch/feedback/service/scheduled.py`. It asks the oncall plugin whether the person just went off shift. It then counts incidents, cases and participants, and sends the questionnaire with those numbers.

- **Fallback window:** if the paging tool gives no `shift_start`, the code sets `hours_in_shift = 7 * 24`, so it looks back 7 days (168 hours). When the start is known, it uses the real shift length (end minus start).
- **Other projects:** yes. The lookups it uses, `incident_service.get_all_last_x_hours` and `case_service.get_all_last_x_hours`, take no `project_id`. They query every incident and case created in the window, across all projects. The code then keeps only the ones whose commander (for incidents) or assignee (for cases) has the on-call person's email. So incidents they led in other projects are counted.
- **Cases:** only cases that have a channel are counted.

The `project_id` filter exists only in the separate `get_all_last_x_hours_by_status` functions, which this code doesn't use.

FILE: src/dispatch/feedback/service/scheduled.py
FUNCTION: find_schedule_and_send
FALLBACK_WINDOW: 7 days (168 hours)
OTHER_PROJECTS: yes