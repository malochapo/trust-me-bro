The function is `find_schedule_and_send` in `src/dispatch/feedback/service/scheduled.py`. It counts incidents where the on-call person is the commander, and cases that have a channel and where they are the assignee, along with their active participants, then sends the questionnaire with those counts.

- **Window when the turn start is unknown:** If the paging tool returns no `shift_start`, it falls back to 7 days (168 hours). When it does return a start, the window is the shift length (`shift_end - shift_start`). Either way, `get_all_last_x_hours` looks back from the current time by `created_at`, not from the shift start.
- **Other projects:** Included. `get_all_last_x_hours` in both `src/dispatch/incident/service.py` and `src/dispatch/case/service.py` doesn't filter by `project_id`, so any incident or case in the same organization whose commander or assignee matches the on-call person's email is counted.

I did not change any code.

FILE: src/dispatch/feedback/service/scheduled.py
FUNCTION: find_schedule_and_send
FALLBACK_WINDOW: 7 days (168 hours)
OTHER_PROJECTS: yes