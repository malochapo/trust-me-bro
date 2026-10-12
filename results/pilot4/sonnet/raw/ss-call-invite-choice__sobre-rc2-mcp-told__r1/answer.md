The function is `filter_participants_for_bridge`. It reads each person's `auto_add_to_incident_bridges` setting, which defaults to true. It is defined in `src/dispatch/incident/flows.py:62`, and the incident flow calls it when it creates the conference (around line 257).

**Is the choice honoured when the incident has a group e-mail address?** No. If the incident has a tactical group, `conference_participants` is set to `[incident.tactical_group.email]`. The filter is never called in that case. Only the group address is invited, and individual opt-outs are not checked. The group's own membership then decides who ends up on the call.

**Are people with no Dispatch account added?** Yes. `auth_service.get_by_email` returns nothing for them, so the function falls into the `else` branch and adds them. The code comment says they can't opt out without an account.

FILE: src/dispatch/incident/flows.py
FUNCTION: filter_participants_for_bridge
APPLIED_WITH_GROUP: no
NO_ACCOUNT_ADDED: yes