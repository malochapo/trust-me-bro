The function is `find_schedule_and_send`. It runs when an on-call shift ends and builds the `num_incidents` and `num_cases` numbers, along with `num_participants`, that go into the feedback message.

**Window:** The count uses the shift's start and end times from the paging tool, so the window is the shift length. If the tool gives no shift start, the code assumes 7 days (168 hours). Incidents and cases are then selected by `created_at` within that window, not by when the shift started.

**Other projects:** Yes. The incident and case queries (`incident_service.get_all_last_x_hours` and `case_service.get_all_last_x_hours`) take no project filter, and the loop matches only on the commander's or assignee's email. The count therefore covers every project in the database session the job runs in. I did not confirm how that session is scoped per organization, so that part of the answer rests on the query shape.

Cases are counted only if they have a channel, and the case-assignee match and participant counts only apply to those. I did not change any code.

- Incidents are counted when the person is `incident.commander`, and cases when they are `case.assignee` with `has_channel` set.
- Participants are counted only for those incidents and cases, using active participants.

Source: `src/dispatch/feedback/service/scheduled.py:96-143`, with the window queries in `src/dispatch/incident/service.py:124` and `src/dispatch/case/service.py:109`.

FILE: src/dispatch/feedback/service/scheduled.py
FUNCTION: find_schedule_and_send
FALLBACK_WINDOW: 168 hours (7 days)
OTHER_PROJECTS: yes