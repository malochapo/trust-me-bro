The choice is honoured in `filter_participants_for_bridge`, but the setup code skips that function when the incident has a group e-mail address. People with no Dispatch account are added to the call.

**Which function honours the choice.** `filter_participants_for_bridge` in `src/dispatch/incident/flows.py:63` looks up each responder's Dispatch user. It keeps them only if their `auto_add_to_incident_bridges` setting is true. That setting is on the user settings model in `auth/models.py` and defaults to true. `incident_create_resources` (`incident/flows.py:257`) calls the function, and the filtered list goes to `conference_flows.create_conference`.

**Incident with a group e-mail address.** No. At `incident/flows.py:253-254`, if `incident.tactical_group` exists, the participant list becomes just that group's e-mail. The filter is only called in the `else` branch, when there is no group. So the opt-out is never checked in the group case. Whoever is in the group is invited through the group address.

**People without a Dispatch account.** Yes, they are added. When `auth_service.get_by_email` finds no user, the function appends the e-mail anyway (`incident/flows.py:79-81`). Its comment says they can't opt out without a user account.

FILE: src/dispatch/incident/flows.py
FUNCTION: filter_participants_for_bridge
APPLIED_WITH_GROUP: no
NO_ACCOUNT_ADDED: yes