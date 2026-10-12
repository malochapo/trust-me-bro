The function that honours the choice is `filter_participants_for_bridge`. It is defined in `src/dispatch/incident/flows.py:63`, and `incident_create_resources` calls it at line 257 when it sets up the conference.

- **How it works:** it looks up each participant's Dispatch user by e-mail and reads their `auto_add_to_incident_bridges` setting. It keeps the e-mail only if that setting is true.
- **Group e-mail address:** no, the choice is not honoured. When `incident.tactical_group` exists, the conference participants are just `[incident.tactical_group.email]`. The filter runs only in the `else` branch, when there is no group, so group members are never checked against their preference.
- **People without an account:** yes, they are added. If no Dispatch user matches the e-mail, the function keeps the address by default, because those people have no way to opt out.

FILE: src/dispatch/incident/flows.py
FUNCTION: filter_participants_for_bridge
APPLIED_WITH_GROUP: no
NO_ACCOUNT_ADDED: yes