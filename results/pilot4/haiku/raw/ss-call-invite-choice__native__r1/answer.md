The function that honours the opt-out is `filter_participants_for_bridge`, in `src/dispatch/incident/flows.py`. It checks each participant's `auto_add_to_incident_bridges` setting and drops anyone who has opted out.

It is not honoured when the incident has a group e-mail address for its responders. In that case the code at lines 253–254 sets the conference participants to just `[incident.tactical_group.email]`, and the filter is never called. Every member of the group is therefore added through the group address, whatever their setting.

People with no Dispatch account are added. The filter's `else` branch (lines 79–81) keeps any e-mail that doesn't match a user, because there is no account in which to store an opt-out.

I did not change any code.

FILE: src/dispatch/incident/flows.py
FUNCTION: filter_participants_for_bridge
APPLIED_WITH_GROUP: no
NO_ACCOUNT_ADDED: yes