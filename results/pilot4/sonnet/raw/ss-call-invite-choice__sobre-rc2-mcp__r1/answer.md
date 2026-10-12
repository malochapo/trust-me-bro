The function that honours the choice is `filter_participants_for_bridge`. It is called from `incident_create_resources` in the same file, when the incident's conference is set up.

- **How it works:** for each participant e-mail, it looks up the Dispatch user. It keeps the person only if their `auto_add_to_incident_bridges` setting is on.
- **Group e-mail:** the choice is not honoured when the incident has a tactical group. In that case the call gets only `[incident.tactical_group.email]`, and the filter is skipped. Individuals' opt-outs only apply in the `else` branch, where there is no group. Whether they end up on the call then depends on the group's membership.
- **No Dispatch account:** these people are added. The function's own comment says they can't opt out without a user account, so it defaults to including them.

FILE: src/dispatch/incident/flows.py
FUNCTION: filter_participants_for_bridge
APPLIED_WITH_GROUP: no
NO_ACCOUNT_ADDED: yes