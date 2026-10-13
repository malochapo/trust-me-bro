The function that honours the opt-out is `filter_participants_for_bridge` in `src/dispatch/incident/flows.py:63`. It is called from the conference setup block in `incident/flows.py` around line 257. It reads each responder's `auto_add_to_incident_bridges` setting, which defaults to `True`, and drops anyone who has turned it off.

- **Group e-mail address:** The choice is not honoured. If the incident has a tactical group, the call is created with only that group's address (`conference_participants = [incident.tactical_group.email]`), and the filter is never run. Every member of the group is then added through the group, regardless of their setting.
- **No Dispatch account:** Those people are kept. The filter adds any e-mail with no matching user, because there is no account in which to record an opt-out. The code comment says so directly.

FILE: src/dispatch/incident/flows.py
FUNCTION: filter_participants_for_bridge
APPLIED_WITH_GROUP: no
NO_ACCOUNT_ADDED: yes