The function is `filter_participants_for_bridge` in `src/dispatch/incident/flows.py`. It is called from `incident_create_resources` (around line 257), when the incident's conference room is created.

- **How the opt-out works:** For each participant email, it looks up a Dispatch user. If one exists, it reads that user's `auto_add_to_incident_bridges` setting (defined in `src/dispatch/auth/models.py`, default `True`) and keeps the email only if the setting is on. A responder who has turned the setting off is dropped from the call.
- **Group e-mail case:** The choice is not honoured. `incident_create_resources` checks `if incident.tactical_group:` first. If the incident has a tactical group, the code sets `conference_participants = [incident.tactical_group.email]` and never calls the filter. Every member of the group's e-mail address is then added, including anyone who opted out. I did not confirm that `group_flows.create_group` always sets `incident.tactical_group` when it runs just above, so the group path may not apply on every incident.
- **No-account case:** People without a Dispatch account are added. The filter's `else` branch keeps any email that has no matching user, with the comment "they can't opt out without a user account".

I made no code changes.

FILE: src/dispatch/incident/flows.py
FUNCTION: filter_participants_for_bridge
APPLIED_WITH_GROUP: no
NO_ACCOUNT_ADDED: yes