The function is `filter_participants_for_bridge`, in `src/dispatch/incident/flows.py:63-82`. It drops a participant only when they have a Dispatch user account and have turned off `auto_add_to_incident_bridges` in their user settings. It is called from `incident_create_resources` (`src/dispatch/incident/flows.py:249-262`) when the conference room is created. `create_conference` in `src/dispatch/conference/flows.py` does no filtering of its own; it passes the list it receives to the conference plugin.

- **Group e-mail:** The choice is not honoured. When the incident has a tactical group, `incident_create_resources` sets the participant list to just `[incident.tactical_group.email]` (line 254). The `else` branch that calls the filter never runs, so every responder is covered by the group address whatever their setting.
- **People without an account:** They are added. The filter keeps any e-mail that has no matching Dispatch user (lines 79-81). Their opt-out is impossible because it lives on a user account.

FILE: src/dispatch/incident/flows.py
FUNCTION: filter_participants_for_bridge
APPLIED_WITH_GROUP: no
NO_ACCOUNT_ADDED: yes