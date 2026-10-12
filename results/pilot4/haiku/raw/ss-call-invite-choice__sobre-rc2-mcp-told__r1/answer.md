The opt-out is enforced by `filter_participants_for_bridge`, but only when the incident has no group e-mail address. With a group address, the opt-out is ignored. People without a Dispatch account are still added.

- **Opt-out setting:** each user's `auto_add_to_incident_bridges` flag (`src/dispatch/auth/models.py:142`), which defaults to on.
- **Filter:** `filter_participants_for_bridge` (`src/dispatch/incident/flows.py:63`) keeps an e-mail only if the matching user has the flag on. If no Dispatch user matches the e-mail, it keeps the address anyway, with the comment "they can't opt out without a user account".
- **Call site:** the conference-room block in the incident setup flow (`src/dispatch/incident/flows.py:255-262`). If `incident.tactical_group` exists, the code passes only the group's e-mail address to `create_conference` and never calls the filter. So with a group address the opt-out has no effect, and members are not checked individually.

I only read the code and did not change anything. I also recorded this as a session finding.

FILE: src/dispatch/incident/flows.py
FUNCTION: filter_participants_for_bridge
APPLIED_WITH_GROUP: no
NO_ACCOUNT_ADDED: yes