The function is `filter_participants_for_bridge`, in `src/dispatch/incident/flows.py`. I read the code only and ran nothing.

- **Which function honours the choice:** `filter_participants_for_bridge` looks up each responder's Dispatch user settings and keeps them only if `auto_add_to_incident_bridges` is true. The incident setup flow in the same file calls it when it creates the conference.
- **Incident with a group e-mail address:** No, the choice is not honoured. When `incident.tactical_group` exists, the setup flow passes `[incident.tactical_group.email]` as the only conference participant and skips the filter. Group members are never checked against their preference. The filter runs only when there is no tactical group.
- **People with no Dispatch account:** Yes, they are added. If no Dispatch user matches the e-mail, the function adds them anyway. Its comment says they can't opt out without an account.

FILE: src/dispatch/incident/flows.py
FUNCTION: filter_participants_for_bridge
APPLIED_WITH_GROUP: no
NO_ACCOUNT_ADDED: yes