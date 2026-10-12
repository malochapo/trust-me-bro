The function is `find_schedule_and_send` in `src/dispatch/feedback/service/scheduled.py`. It counts incidents and cases for the outgoing on-call person, then passes the totals to `send_oncall_shift_feedback_message`.

- **Counting:** An incident counts when the person is its commander. A case counts only if it has a channel and its assignee is that person. Participant counts come from active participants on those records.
- **Fallback window:** When the paging tool gives no shift start, the window is `7 * 24` hours, which is 168 hours (7 days). Otherwise the window is the shift length in hours, computed from shift start and end.
- **Other projects:** The incident and case queries (`get_all_last_x_hours` in `src/dispatch/incident/service.py` and `src/dispatch/case/service.py`) filter only on `created_at`, not `project_id`. Records from every project visible to that database session are counted, so incidents this person led in other projects of the same organization are included. I inferred the organization boundary from the absence of a project filter and did not confirm how sessions are scoped to an organization.

FILE: src/dispatch/feedback/service/scheduled.py
FUNCTION: find_schedule_and_send
FALLBACK_WINDOW: 168 hours
OTHER_PROJECTS: yes