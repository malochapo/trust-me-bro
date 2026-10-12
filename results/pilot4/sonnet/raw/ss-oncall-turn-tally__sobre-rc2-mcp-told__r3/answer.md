The counts are worked out in `find_schedule_and_send`, in `src/dispatch/feedback/service/scheduled.py`. It gets the shift end and start from the paging tool's `did_oncall_just_go_off_shift`. It then counts incidents where the person was commander, and cases that have a channel and where they were assignee. It also counts active participants across those.

- **Fallback window:** if the paging tool gives no shift start, `hours_in_shift` defaults to `7 * 24` hours, so 7 days.
- **Other projects:** yes. The lookups, `incident_service.get_all_last_x_hours` and `case_service.get_all_last_x_hours`, filter only on `created_at`. They take no project filter, so incidents and cases in other projects of the organization are included if the commander or assignee's email matches the on-call person's.

I didn't change any code.

FILE: src/dispatch/feedback/service/scheduled.py
FUNCTION: find_schedule_and_send
FALLBACK_WINDOW: 7 days (168 hours)
OTHER_PROJECTS: yes