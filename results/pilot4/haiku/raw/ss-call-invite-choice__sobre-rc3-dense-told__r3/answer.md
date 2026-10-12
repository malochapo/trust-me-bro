The opt-out is honoured through `filter_participants_for_bridge`, but only when the incident has no tactical group e-mail. With a group address, the call is set up with the group address alone, so the opt-out is not applied. People without a Dispatch account are added by default.

- **The filter:** `filter_participants_for_bridge` (`src/dispatch/incident/flows.py:63`) keeps a responder only if their user settings have `auto_add_to_incident_bridges` set. Anyone with no Dispatch user is kept.
- **The caller:** `incident_create_resources` (`src/dispatch/incident/flows.py:248-262`) builds the conference's participant list. If `incident.tactical_group` exists, the list is just `[incident.tactical_group.email]` and the filter is never called. Otherwise the list is the tactical participants passed through the filter, and `conference_flows.create_conference` (`src/dispatch/conference/flows.py:14`) receives that list.
- **Group case:** Whoever is a member of the group e-mail gets on the call, whatever their opt-out setting. Members of that group who have no Dispatch account are also on it.

I did not change any code. I also saved this as a finding in sobre.

FILE: src/dispatch/incident/flows.py
FUNCTION: filter_participants_for_bridge
APPLIED_WITH_GROUP: no
NO_ACCOUNT_ADDED: yes