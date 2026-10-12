The function that honours the choice is `filter_participants_for_bridge`, in `src/dispatch/incident/flows.py:63`. I read the code only and ran nothing.

**How it works.** For each participant e-mail it looks up the Dispatch user and loads their settings. It keeps the e-mail only if `auto_add_to_incident_bridges` is true. The incident flow calls it at `incident/flows.py:248-262`, just before `conference_flows.create_conference`. `create_conference` itself does no filtering.

**Group e-mail.** The choice is not honoured when the incident has a tactical group. In that case the participant list is set to `[incident.tactical_group.email]` and `filter_participants_for_bridge` is never called. The filter only runs in the `else` branch, when there is no tactical group. Anyone in the group is therefore added to the call whatever their setting says.

**People without an account.** They are added. When no Dispatch user matches the e-mail, the function appends it anyway. Its comment says they can't opt out without a user account.

FILE: src/dispatch/incident/flows.py
FUNCTION: filter_participants_for_bridge
APPLIED_WITH_GROUP: no
NO_ACCOUNT_ADDED: yes