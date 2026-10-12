The function is `find_schedule_and_send` in `src/dispatch/feedback/service/scheduled.py`. It is called from `oncall_shift_feedback`, and it builds the `num_incidents`, `num_cases` and `num_participants` numbers that go into the questionnaire message.

- **Turn start:** The turn length comes from the paging tool's `shift_start` and `shift_end` (via `did_oncall_just_go_off_shift`). If `shift_start` is missing, `hours_in_shift` defaults to `7 * 24`.
- **Counting:** Incidents count when the person is the commander. Cases count only when `case.has_channel` is true and the person is the assignee. Both are filtered by `created_at >= now - hours`, using `get_all_last_x_hours` in `incident/service.py` and `case/service.py`.
- **Other projects:** Both `get_all_last_x_hours` queries have no `project_id` filter, and `find_schedule_and_send` does not add one. Incidents or cases they led in other projects are therefore counted, as long as they are in the same tenant database.

One detail: the window is measured back from the time the feedback job runs, not from the recorded shift start. For a known shift, that is roughly the shift length.

FILE: src/dispatch/feedback/service/scheduled.py
FUNCTION: find_schedule_and_send
FALLBACK_WINDOW: 168 hours (7 days)
OTHER_PROJECTS: yes