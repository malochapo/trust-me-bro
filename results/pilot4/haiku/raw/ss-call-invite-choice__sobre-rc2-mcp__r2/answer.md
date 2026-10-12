The function is `filter_participants_for_bridge` in `src/dispatch/incident/flows.py:63`. It is called from the conference-setup block of the incident flow at `src/dispatch/incident/flows.py:255-261`.

- **How the choice is honoured:** Each responder's `auto_add_to_incident_bridges` setting (`src/dispatch/auth/models.py:142`, default `True`) is checked. Only people whose setting is on are kept in the participant list passed to `conference_flows.create_conference`.
- **Group e-mail case:** The choice is not honoured. If the incident has a tactical group, the code at lines 255-256 skips the filter and passes only the group's e-mail address to the conference plugin. Every member of that group is then reached through the group, whatever their setting.
- **People without a Dispatch account:** They are added. The function's `else` branch keeps any address with no matching user, with the comment that they "can't opt out without a user account".

I did not change any code.

FILE: src/dispatch/incident/flows.py
FUNCTION: filter_participants_for_bridge
APPLIED_WITH_GROUP: no
NO_ACCOUNT_ADDED: yes