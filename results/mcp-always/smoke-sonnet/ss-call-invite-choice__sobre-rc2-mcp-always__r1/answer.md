The function that honours the opt-out is `filter_participants_for_bridge`, defined in `src/dispatch/incident/flows.py:63`. `incident_create_resources` calls it just before `conference_flows.create_conference` (lines 257–262).

- **How the choice is applied:** For each responder e-mail, the function looks up the Dispatch user. It then reads that user's `auto_add_to_incident_bridges` setting, which defaults to true. The address is kept only if the setting is true.
- **Incident with a group e-mail:** No, the choice is not honoured. When `incident.tactical_group` exists, `incident_create_resources` passes `[incident.tactical_group.email]` as the conference participants (lines 253–254). `filter_participants_for_bridge` is only called in the `else` branch, so the group's members are never filtered individually.
- **People without a Dispatch account:** Yes, they are added. If no Dispatch user matches the e-mail, the function keeps the address (lines 79–81). Its comment says they can't opt out without an account.

I only read the code and changed nothing.

FILE: src/dispatch/incident/flows.py
FUNCTION: filter_participants_for_bridge
APPLIED_WITH_GROUP: no
NO_ACCOUNT_ADDED: yes