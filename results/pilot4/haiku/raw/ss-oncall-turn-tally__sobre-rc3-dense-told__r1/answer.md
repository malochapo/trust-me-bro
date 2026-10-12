The counts are computed in `find_schedule_and_send`. When the paging tool gives no shift start, the lookback is 7 days. Incidents led in other projects of the organization are included.

- **Function:** `find_schedule_and_send` builds the `num_incidents` and `num_cases` values and passes them to the feedback message. Its caller is `oncall_shift_feedback`, which runs on a schedule.
- **Turn start:** The window comes from the paging tool's `shift_start` and `shift_end`, which set `hours_in_shift`. If `shift_start` is missing, `hours_in_shift` defaults to `7 * 24` (168 hours).
- **Other projects:** `get_all_last_x_hours` in both `incident/service.py` and `case/service.py` filters only on `created_at`, not `project_id`. The on-call person is matched by commander or assignee email, so incidents and cases they led in other projects are counted. The schema is per organization (the `tenant` migrations), so the scope is the organization.

Two details matter when reading the counts. Incidents and cases are matched by `created_at` within the window, not by when the person held the role. Cases are only counted when `case.has_channel` is true. I did not run the code. I recorded this finding in the sobre session.

FILE: src/dispatch/feedback/service/scheduled.py
FUNCTION: find_schedule_and_send
FALLBACK_WINDOW: 168 hours
OTHER_PROJECTS: yes