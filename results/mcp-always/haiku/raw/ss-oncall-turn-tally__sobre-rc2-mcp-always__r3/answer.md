The function is `find_schedule_and_send` in `src/dispatch/feedback/service/scheduled.py`. It counts incidents and cases for the outgoing on-call person and passes the totals to the feedback message.

When the paging tool gives no shift start, `hours_in_shift` defaults to `7 * 24`, so the window is 7 days (168 hours). Otherwise the window is the shift length, computed from the shift start and end times.

Yes, other projects are included. The counts come from `incident_service.get_all_last_x_hours` and `case_service.get_all_last_x_hours`, which filter only on `created_at` and never on `project_id`. The only per-project filter is on the scheduled task, not on these queries. So any incident where the on-call person is the commander counts, whatever project it is in. Cases count only if they have a channel and that person is the assignee.

FILE: src/dispatch/feedback/service/scheduled.py
FUNCTION: find_schedule_and_send
FALLBACK_WINDOW: 7 days
OTHER_PROJECTS: yes