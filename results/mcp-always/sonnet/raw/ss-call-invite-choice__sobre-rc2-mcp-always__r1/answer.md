**Which function honours the choice:** `filter_participants_for_bridge`. It looks up each responder's Dispatch user and keeps them only if their `auto_add_to_incident_bridges` setting is on. `incident_create_resources` calls it just before it creates the conference with `conference_flows.create_conference`.

**When the incident has a group e-mail address:** No, the choice is not honoured. In `incident_create_resources`, when `incident.tactical_group` exists, the participant list is just `[incident.tactical_group.email]`. The `else` branch is the only one that calls the filter. The group's membership is never checked against anyone's preference. A responder who opted out is still in the call through the group address, assuming the group contains them. The tactical group is created from the unfiltered participant emails earlier in the same function.

**People without a Dispatch account:** Yes, they are added. When `auth_service.get_by_email` finds no user, the filter appends the e-mail anyway. The code comment says they can't opt out without an account. This only applies in the no-group path.

I didn't run anything or change any code.

FILE: src/dispatch/incident/flows.py
FUNCTION: filter_participants_for_bridge
APPLIED_WITH_GROUP: no
NO_ACCOUNT_ADDED: yes