The counting is done in `find_schedule_and_send` in `src/dispatch/feedback/service/scheduled.py`. I only read the code and changed nothing.

- **Which function:** `find_schedule_and_send` (line 77) gets the person who just went off shift from the oncall plugin's `did_oncall_just_go_off_shift`. It counts incidents where they are the commander and cases with a channel where they are the assignee. It also counts active participants. It then passes these counts as `details` to `send_oncall_shift_feedback_message`.
- **Fallback window:** if the plugin gives no `shift_start`, it uses `hours_in_shift = 7 * 24`, which is 7 days (168 hours).
- **Other projects:** yes, they are included. The lookup is `incident_service.get_all_last_x_hours` (`src/dispatch/incident/service.py:124`). It filters only on `created_at`, not on project. `find_schedule_and_send` doesn't filter by project either. It matches on the commander's email, so an incident they led in any project of the organization is counted. I read the incident lookup but not `case_service.get_all_last_x_hours`, which cases use. The cases loop applies the same email filter. I'd expect the case lookup to behave the same way, but I haven't confirmed it.

FILE: src/dispatch/feedback/service/scheduled.py
FUNCTION: find_schedule_and_send
FALLBACK_WINDOW: 7 days
OTHER_PROJECTS: yes