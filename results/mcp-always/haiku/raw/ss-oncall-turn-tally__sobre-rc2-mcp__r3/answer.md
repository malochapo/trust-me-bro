The function is `find_schedule_and_send` in `src/dispatch/feedback/service/scheduled.py`. It finds the turn that just ended via PagerDuty, then counts incidents and cases where that person is the commander or assignee, plus their active participants. The shift start comes from `oncall_shift_check` in `src/dispatch/plugins/dispatch_pagerduty/service.py`, which walks back in 24-hour steps to find where the turn began. When the start is unknown, the code uses a 7-day window (`hours_in_shift = 7 * 24`). Incident and case counting is by person email, and the `get_all_last_x_hours` queries in `incident/service.py` and `case/service.py` don't filter by project. So incidents they led in other projects are counted too. I didn't change any code.

FILE: src/dispatch/feedback/service/scheduled.py
FUNCTION: find_schedule_and_send
FALLBACK_WINDOW: 168 hours (7 days)
OTHER_PROJECTS: yes