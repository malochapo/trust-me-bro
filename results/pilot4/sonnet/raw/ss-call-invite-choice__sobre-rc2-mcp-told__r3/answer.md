The function that honours the choice is `filter_participants_for_bridge`. It checks each person's `auto_add_to_incident_bridges` setting, which defaults to true.

**Where it is called.** `incident_create_resources`, in `incident/flows.py` around line 250, calls it when the incident has no conference yet. The result is passed to `conference_flows.create_conference`. That function in `conference/flows.py` doesn't filter anything itself.

**Incidents with a group e-mail address.** The choice is not honoured. When the incident has a tactical group, the participant list is just `[incident.tactical_group.email]`. The filter only runs in the `else` branch, when there is no tactical group. In that case the call is set up with the group address, so every group member is covered regardless of their setting.

**People without a Dispatch account.** They are added. If `auth_service.get_by_email` finds no user, the function appends the e-mail anyway. A comment in the code says they can't opt out without an account. This only applies on the no-group path.

FILE: src/dispatch/incident/flows.py
FUNCTION: filter_participants_for_bridge
APPLIED_WITH_GROUP: no
NO_ACCOUNT_ADDED: yes