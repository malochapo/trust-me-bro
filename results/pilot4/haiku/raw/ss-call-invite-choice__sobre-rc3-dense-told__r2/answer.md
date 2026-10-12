The function that honours the opt-out is `filter_participants_for_bridge`, in `src/dispatch/incident/flows.py:63`. It is called from `incident_create_resources` (`flows.py:179`), which sets up the conference room.

- **How the choice works:** the function checks each participant's `auto_add_to_incident_bridges` user setting (`src/dispatch/auth/models.py:142`, default `True`). Anyone who has turned it off is dropped from the call.
- **Group e-mail case:** the choice is not honoured. `incident_create_resources` only calls the filter when the incident has no tactical group. If it has one, the conference is created with only `incident.tactical_group.email` as a participant, and the per-user setting is never checked. Members of that group are therefore all on the call, whatever they chose.
- **No Dispatch account:** these people are added. The filter has an `else` branch for e-mails with no matching user and appends them, with the comment that they "can't opt out without a user account".

I only read the code and changed nothing. I did not run the flow.

FILE: src/dispatch/incident/flows.py
FUNCTION: filter_participants_for_bridge
APPLIED_WITH_GROUP: no
NO_ACCOUNT_ADDED: yes