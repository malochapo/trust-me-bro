The function that honours the opt-out is `filter_participants_for_bridge`, in `src/dispatch/incident/flows.py:63`. It checks each responder's `auto_add_to_incident_bridges` user setting and drops anyone who has turned it off. It is called from the incident setup flow in the same file, around line 253, only when the incident has no tactical group.

- **With a group e-mail address:** the choice is not honoured. When `incident.tactical_group` exists, the flow passes only the group's address to `create_conference`, and the filter is skipped. The tactical group itself is built from every individual participant, unfiltered (around line 216), so opted-out responders are still on the call through group membership.
- **People with no Dispatch account:** they are added. The filter has no user record to check for them, so it keeps their e-mail address by default. The code comment says they "can't opt out without a user account".

FILE: src/dispatch/incident/flows.py
FUNCTION: filter_participants_for_bridge
APPLIED_WITH_GROUP: no
NO_ACCOUNT_ADDED: yes