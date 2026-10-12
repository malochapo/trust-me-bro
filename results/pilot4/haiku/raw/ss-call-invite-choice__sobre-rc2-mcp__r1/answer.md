The function that honours the choice is `filter_participants_for_bridge`, defined in `src/dispatch/incident/flows.py`. It checks each person's `auto_add_to_incident_bridges` setting, and it is only applied when the incident has no tactical group.

- **Group e-mail:** The choice is not honoured. When `incident.tactical_group` exists, the conference is created with only the group's address (`conference_participants = [incident.tactical_group.email]`), and the filter is never called. Everyone in the group is then on the call, whatever their setting. Group membership is managed separately, so opted-out responders can still end up on the call through it.
- **No Dispatch account:** Those people are added. The filter's own comment says it defaults to adding them because they have no account in which to opt out.

I did not change any code.

FILE: src/dispatch/incident/flows.py
FUNCTION: filter_participants_for_bridge
APPLIED_WITH_GROUP: no
NO_ACCOUNT_ADDED: yes