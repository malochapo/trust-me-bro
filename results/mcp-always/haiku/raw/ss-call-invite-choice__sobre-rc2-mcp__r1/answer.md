The function that honours the choice is `filter_participants_for_bridge`. It checks each participant's `auto_add_to_incident_bridges` setting and drops anyone who has opted out. It is called from the incident setup flow in `src/dispatch/incident/flows.py` (around line 257), only when the incident has no tactical group.

- **Group e-mail address:** When the incident has a tactical group, the setup code passes only `[incident.tactical_group.email]` to the conference, and the filter never runs. The opt-out is ignored, and the whole group is added to the call.
- **No Dispatch account:** `filter_participants_for_bridge` has no settings to check for these people, so it keeps them. They are added to the call.

`create_conference` in `src/dispatch/conference/flows.py` does not apply any opt-out. It passes the list it receives to the conference plugin.

I did not change any code.

FILE: src/dispatch/incident/flows.py
FUNCTION: filter_participants_for_bridge
APPLIED_WITH_GROUP: no
NO_ACCOUNT_ADDED: yes