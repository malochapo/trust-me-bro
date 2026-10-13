The function that honours the opt-out is `filter_participants_for_bridge`, defined in `src/dispatch/incident/flows.py:63`. It checks each participant's `auto_add_to_incident_bridges` setting and drops anyone who has opted out. Its only caller is `incident_create_resources` (`flows.py:257`).

- **With a group e-mail address:** the choice is not honoured. When the incident has a tactical group, `incident_create_resources` passes only `[incident.tactical_group.email]` as the conference participant (`flows.py:252-254`). The `else` branch that runs the filter is skipped, so the opt-out setting is never checked and everyone in the group is on the call.
- **Without a group:** the filter runs. Users who have opted out are removed, and everyone else on the incident's tactical participant list is added.
- **People with no Dispatch account:** they are added. The filter has no user record to check for them, so it keeps them, as its own comment says ("they can't opt out without a user account").

FILE: src/dispatch/incident/flows.py
FUNCTION: filter_participants_for_bridge
APPLIED_WITH_GROUP: no
NO_ACCOUNT_ADDED: yes