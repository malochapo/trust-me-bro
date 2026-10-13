The function is `filter_participants_for_bridge`, in `src/dispatch/incident/flows.py:63`. It is called from `incident_create_resources` (`src/dispatch/incident/flows.py:260`) when the incident has no conference yet.

- **How the choice is honoured:** For each participant email, it looks up the Dispatch user. If that user's settings have `auto_add_to_incident_bridges` turned on, the email is kept. If it is off, the email is dropped.
- **Group e-mail address:** No. When the incident has a tactical group (`incident.tactical_group`), `incident_create_resources` sets the conference participants to just `[incident.tactical_group.email]` (lines 252–254). The `else` branch that calls the filter never runs, so the opt-out is ignored and the group address is invited as a whole.
- **People without an account:** They are added. The filter's comment says so: with no matching Dispatch user, the address is kept because such people cannot opt out.

I did not change any code.

FILE: src/dispatch/incident/flows.py
FUNCTION: filter_participants_for_bridge
APPLIED_WITH_GROUP: no
NO_ACCOUNT_ADDED: yes