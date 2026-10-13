The counting is done by `find_schedule_and_send`, and I've now read everything that decides your other two questions.

- **Which function:** `find_schedule_and_send` in `src/dispatch/feedback/service/scheduled.py` does the counting. It asks the oncall plugin whether the person just went off shift. It then counts incidents where they were commander and cases with a channel where they were assignee. It passes those counts, plus a participant count, to `send_oncall_shift_feedback_message`, which sends the questionnaire.
- **Fallback window:** If the paging tool gives no `shift_start`, the code sets `hours_in_shift = 7 * 24`. That is a 7-day lookback. When the start is known, the window is the shift length, from start to end.
- **Other projects:** Yes. `incident_service.get_all_last_x_hours` and `case_service.get_all_last_x_hours` filter only on `created_at`, not on `project_id`. The loop then matches on the commander's or assignee's email. The `project` argument only picks the oncall plugin and the individual record. I'm assuming the database session is limited to one organization (Dispatch's per-organization tenant schemas), so the count covers all projects in that organization. I didn't check how the session is scoped.

I changed no code.

FILE: src/dispatch/feedback/service/scheduled.py
FUNCTION: find_schedule_and_send
FALLBACK_WINDOW: 7 days (168 hours)
OTHER_PROJECTS: yes