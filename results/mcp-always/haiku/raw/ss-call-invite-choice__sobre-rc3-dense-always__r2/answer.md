The function that honours the opt-out is `filter_participants_for_bridge`, but only when the incident has no group address. With a group, the opt-out is ignored. People without a Dispatch account are added.

- **Where the choice is applied:** `filter_participants_for_bridge` looks up each participant's Dispatch user by e-mail and keeps them only if `auto_add_to_incident_bridges` is set in their user settings (`src/dispatch/incident/flows.py:63-82`).
- **Group e-mail case:** `incident_create_resources` only calls that filter when the incident has no tactical group. If it has one, the conference participants are set to `[incident.tactical_group.email]` (`src/dispatch/incident/flows.py:252-259`). The opt-out is never checked, so the group address is what gets added to the call.
- **No-account case:** when no Dispatch user matches the e-mail, the function adds the address anyway. Its own comment says people without an account "can't opt out."
- **Call creation:** `create_conference` in `src/dispatch/conference/flows.py` passes the list it receives straight to the conference plugin, so it applies no further filtering.

I did not change any code.

FILE: src/dispatch/incident/flows.py
FUNCTION: filter_participants_for_bridge
APPLIED_WITH_GROUP: no
NO_ACCOUNT_ADDED: yes