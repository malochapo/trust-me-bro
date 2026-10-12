The function is `find_schedule_and_send` in `src/dispatch/feedback/service/scheduled.py`. It counts incidents and cases for the outgoing on-call person and sends them with the questionnaire. I did not change any code.

- **Turn start known:** the window is the shift length, computed as shift end minus shift start from the PagerDuty `did_oncall_just_go_off_shift` result.
- **Turn start unknown:** it falls back to `hours_in_shift = 7 * 24`, so the last 7 days.
- **Other projects:** the incident and case lookups (`incident_service.get_all_last_x_hours`, `case_service.get_all_last_x_hours`) filter only on creation time, with no project filter. Incidents are matched by commander email and cases by assignee email, so incidents they led in other projects are included as long as they fall in the window. The lookups do not check for a `project_id` filter on any other field.

Also note: incidents are counted by commander only, while cases require `case.has_channel` and an assignee match.

FILE: src/dispatch/feedback/service/scheduled.py
FUNCTION: find_schedule_and_send
FALLBACK_WINDOW: 7 days
OTHER_PROJECTS: yes