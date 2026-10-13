The function is `find_schedule_and_send` in `src/dispatch/feedback/service/scheduled.py`. It runs when a shift has ended, takes the on-call person's email from the paging tool, and builds the `num_incidents`, `num_cases` and `num_participants` figures that go into the questionnaire.

- **Shift start unknown:** if the paging tool returns no `shift_start`, the function sets the window to `7 * 24` hours, which is 7 days (`scheduled.py:120-121`). When the start is known, the window is the shift's length in hours, computed from `shift_end - shift_start`.
- **Window anchor:** the incident and case queries count items created in the last N hours from the current UTC time (`incident/service.py:124-129`, `case/service.py:109-112`). The window is not anchored to the shift's actual start and end.
- **Other projects:** the incident and case queries filter only on `created_at`, not on `project_id`. Incidents and cases are therefore counted across every project in the organization's database. They are attributed to the person by commander email for incidents (`scheduled.py:128`) and by assignee email for cases, which must also have a channel (`scheduled.py:134`).

Nothing was changed in the code.

FILE: src/dispatch/feedback/service/scheduled.py
FUNCTION: find_schedule_and_send
FALLBACK_WINDOW: 7 days (168 hours)
OTHER_PROJECTS: yes