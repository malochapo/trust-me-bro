The choice is honoured by `filter_participants_for_bridge`, in `src/dispatch/incident/flows.py`. It checks each participant's `auto_add_to_incident_bridges` setting and drops anyone who has opted out. The caller is the conference-creation block in `incident_create_flow`, around lines 253–264. I did not change any code.

- **Group e-mail address:** No. If the incident has a tactical group, the block passes only `[incident.tactical_group.email]` to `create_conference`, and the filter is never called. The opt-out is ignored, and everyone in that group is added to the call.
- **No Dispatch account:** Yes, they are added. The filter only checks people it can match to a Dispatch user. If `auth_service.get_by_email` finds no user, the code keeps the address with the comment "they can't opt out without a user account".

FILE: src/dispatch/incident/flows.py
FUNCTION: filter_participants_for_bridge
APPLIED_WITH_GROUP: no
NO_ACCOUNT_ADDED: yes