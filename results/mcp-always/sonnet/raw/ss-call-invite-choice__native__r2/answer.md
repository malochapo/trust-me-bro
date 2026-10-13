The function that honours the choice is `filter_participants_for_bridge`. It's in `src/dispatch/incident/flows.py:63`. `incident_create_resources` calls it when it sets up the incident's conference.

- **How it works:** it looks up each participant's Dispatch user by e-mail and reads their settings. It keeps the person only if `auto_add_to_incident_bridges` is true. A person who has turned that off is left off the call.
- **Group e-mail address:** no, the choice is not honoured in that case. In `incident_create_resources` (lines 252–259), if `incident.tactical_group` exists, the conference participants become just `[incident.tactical_group.email]` and the filter is skipped. The filter only runs in the `else` branch, when there is no tactical group. Anyone in that group is invited through the group address whatever they chose.
- **People without an account:** yes, they are added. The function's `else` branch keeps any e-mail with no matching Dispatch user, since they can't opt out without an account.

FILE: src/dispatch/incident/flows.py
FUNCTION: filter_participants_for_bridge
APPLIED_WITH_GROUP: no
NO_ACCOUNT_ADDED: yes