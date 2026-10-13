The function that works out the numbers is `find_schedule_and_send`, in `src/dispatch/feedback/service/scheduled.py`. It is called from `oncall_shift_feedback`, which runs from the two daily schedulers.

- **How the window is set:** it takes the shift length from PagerDuty's shift start and end. If the paging tool does not return a shift start, it falls back to `7 * 24 = 168` hours.
- **Counting:** it calls `incident_service.get_all_last_x_hours` and `case_service.get_all_last_x_hours`. Both count records by `created_at` going back from now, not by the shift's own start and end. Incidents count when the person is the commander. Cases count only when they have a channel and the person is the assignee. Participants are counted from the active ones on each.
- **Other projects:** neither `get_all_last_x_hours` function filters by project. An incident or case the person led in another project of the same organization is therefore counted, provided it falls in the window.

I did not change any code.

FILE: src/dispatch/feedback/service/scheduled.py
FUNCTION: find_schedule_and_send
FALLBACK_WINDOW: 168 hours
OTHER_PROJECTS: yes