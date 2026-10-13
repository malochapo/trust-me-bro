The function that honours the choice is `filter_participants_for_bridge`. It is defined in `src/dispatch/incident/flows.py` at line 63.

- **How it works:** For each responder e-mail, it looks up the Dispatch user. It then reads that user's settings and keeps the e-mail only if `auto_add_to_incident_bridges` is true. The incident setup flow in the same file calls it and passes the resulting list to `conference_flows.create_conference`.
- **Group e-mail case:** The choice is not honoured when the incident has a tactical group. In that case the flow passes `[incident.tactical_group.email]` as the only participant and skips the filter (`incident/flows.py:252-259`). Anyone in the group is therefore invited, whatever they chose. The filter only runs when there is no tactical group.
- **People without an account:** They are added. The function's own comment says they can't opt out without a user account, so the e-mail is kept.

FILE: src/dispatch/incident/flows.py
FUNCTION: filter_participants_for_bridge
APPLIED_WITH_GROUP: no
NO_ACCOUNT_ADDED: yes