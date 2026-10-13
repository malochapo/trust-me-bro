The function is `filter_participants_for_bridge` in `src/dispatch/incident/flows.py`, at line 63. It checks each participant's `auto_add_to_incident_bridges` setting and drops anyone who has opted out.

It is only applied when the incident has no tactical group. In `incident_create_resources` (around lines 251–259), if `incident.tactical_group` exists, the conference is created with the tactical group's e-mail address as its only participant. The filter never runs, so the opt-out is not honoured for group-based incidents. Whether opted-out responders still end up on the call then depends on the group's membership, which this code does not check.

People with no Dispatch account are always added. The function's `else` branch appends any e-mail that doesn't match a user, with the comment "they can't opt out without a user account".

FILE: src/dispatch/incident/flows.py
FUNCTION: filter_participants_for_bridge
APPLIED_WITH_GROUP: no
NO_ACCOUNT_ADDED: yes