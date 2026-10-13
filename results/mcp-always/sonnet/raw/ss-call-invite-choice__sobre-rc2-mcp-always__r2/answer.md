The function that honours the choice is `filter_participants_for_bridge`, at `src/dispatch/incident/flows.py:63`. `incident_create_resources` (same file, around line 248) calls it before `conference_flows.create_conference` sets up the call. For each responder e-mail, it looks up the Dispatch user and reads their settings. It keeps the person only if `auto_add_to_incident_bridges` is true.

**Incident with a group e-mail address:** No, the choice is not honoured. In `incident_create_resources`, if `incident.tactical_group` exists, the participant list is just `[incident.tactical_group.email]`. The filter runs only in the `else` branch, when there is no group. So when a group exists, everyone in that group is invited and nobody's opt-out is checked.

**People without a Dispatch account:** Yes, they are added. When `auth_service.get_by_email` finds no user, the function appends the e-mail anyway. A comment in the code explains that such people can't opt out without an account.

FILE: src/dispatch/incident/flows.py
FUNCTION: filter_participants_for_bridge
APPLIED_WITH_GROUP: no
NO_ACCOUNT_ADDED: yes