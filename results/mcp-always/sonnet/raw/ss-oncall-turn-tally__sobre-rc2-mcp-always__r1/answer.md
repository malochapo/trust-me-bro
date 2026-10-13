The numbers are worked out inside `find_schedule_and_send` in `src/dispatch/feedback/service/scheduled.py`, starting at line 77. `oncall_shift_feedback` calls it once per on-call schedule. It counts incidents led, cases handled and participants, then passes them as `details` to `send_oncall_shift_feedback_message`.

**Fallback window.** If the paging tool gives no `shift_start`, the code uses `hours_in_shift = 7 * 24`, which is 7 days (168 hours), at `scheduled.py:121`.

**Other projects.** Yes, they are included. The lookup is `incident_service.get_all_last_x_hours` (`incident/service.py:124`). It filters only on `Incident.created_at` and has no project filter. The loop then keeps incidents where `incident.commander.individual.email` matches the on-call person's email. An incident they led in another project of the organization is therefore counted. `case_service.get_all_last_x_hours` is called the same way for cases. I did not open that function, so I'm assuming it also has no project filter. Cases are also required to have a channel (`case.has_channel`).

FILE: src/dispatch/feedback/service/scheduled.py
FUNCTION: find_schedule_and_send
FALLBACK_WINDOW: 7 days
OTHER_PROJECTS: yes