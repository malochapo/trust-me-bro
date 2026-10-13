The numbers come from `find_schedule_and_send` in `src/dispatch/feedback/service/scheduled.py`. It calls `did_oncall_just_go_off_shift` on the paging plugin. It then counts incidents and cases whose commander or assignee email matches the person who went off shift. It also counts the active participants in each of those.

- **Fallback window:** if the plugin doesn't return a `shift_start`, `hours_in_shift` defaults to `7 * 24`, which is 7 days (168 hours). When a start is given, the window is the shift's own length, from `shift_start` to `shift_end`. Either way the look-back is measured from the current time.
- **Other projects:** yes. `incident_service.get_all_last_x_hours` and `case_service.get_all_last_x_hours` filter only on `created_at`, with no `project_id` filter. Incidents and cases from every project are therefore included. The only link to the person is their email matching the commander's or the assignee's.
  - I read "other projects of the same organization" as other projects in the same database. I didn't check whether those queries are also limited to one organization elsewhere.
  - The project is only used to look up the individual and to send the message.
- **Cases:** a case counts only if it has a channel (`case.has_channel`).

FILE: src/dispatch/feedback/service/scheduled.py
FUNCTION: find_schedule_and_send
FALLBACK_WINDOW: 7 days
OTHER_PROJECTS: yes