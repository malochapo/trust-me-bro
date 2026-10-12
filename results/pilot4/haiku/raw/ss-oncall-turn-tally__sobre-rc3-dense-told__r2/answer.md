The function is `find_schedule_and_send`. It counts incidents and cases for the departing on-call person and passes the totals to the questionnaire message.

- **Counting:** An incident counts when the person is its commander. A case counts when it has a channel and the person is its assignee. Participants with at least one active role are summed for each.
- **Window:** The start of the turn comes from `did_oncall_just_go_off_shift`. If that start is missing, the function falls back to `7 * 24 = 168` hours, which is 7 days. It is the lookback from the current time, not the shift end.
- **Other projects:** Included. `get_all_last_x_hours` in both `incident/service.py` and `case/service.py` filters only on `created_at`, not on `project_id`. The commander and assignee checks don't restrict by project either, so incidents they led in other projects of the same organization count. Tenant schemas are per organization, so the query is effectively organization-wide.

I didn't change any code. I recorded the finding in the sobre session.

FILE: src/dispatch/feedback/service/scheduled.py
FUNCTION: find_schedule_and_send
FALLBACK_WINDOW: 168 hours (7 days)
OTHER_PROJECTS: yes