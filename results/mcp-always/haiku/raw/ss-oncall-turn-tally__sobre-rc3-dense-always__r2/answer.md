The function is `find_schedule_and_send`, in `src/dispatch/feedback/service/scheduled.py` (line 77). It is called from `oncall_shift_feedback`, which runs at the handoff hour. It counts the incidents and cases for the outgoing on-call person and sends the result through `send_oncall_shift_feedback_message`.

- **Counting:** It takes the shift length from the paging tool's shift start and end times. It counts incidents whose commander has the on-call person's email, and cases that have a channel and whose assignee has that email. Both counts use `created_at` within that window. It also sums active participants.
- **Fallback:** If the paging tool gives no shift start, `hours_in_shift` is set to `7 * 24`, so it looks back 168 hours (7 days) from the current time.
- **Other projects:** Yes. The incident and case queries (`get_all_last_x_hours` in `src/dispatch/incident/service.py:124` and `src/dispatch/case/service.py:109`) filter only on time, with no project filter. The commander and assignee match is on email, not project. The session is passed in from a project-scoped job, but the queries don't use that project to filter. I didn't check how the database session is scoped, so the "yes" depends on the session covering the whole organization.

FILE: src/dispatch/feedback/service/scheduled.py
FUNCTION: find_schedule_and_send
FALLBACK_WINDOW: 168 hours (7 days)
OTHER_PROJECTS: yes