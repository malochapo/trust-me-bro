The function that honours the choice is `filter_participants_for_bridge`. It's defined in `src/dispatch/incident/flows.py:63`.

- **How it works:** the incident flow (around line 248) calls it before it calls `conference_flows.create_conference`. For each responder e-mail it looks up the Dispatch user and reads their `auto_add_to_incident_bridges` setting. It keeps the e-mail only if that setting is on.
- **Incident with a group e-mail:** the choice is not honoured. If `incident.tactical_group` exists, the participant list becomes just `[incident.tactical_group.email]` and the filter is skipped. The group address is invited as a whole.
- **People without a Dispatch account:** they are added. With no user record there is no setting to read, so the function keeps them by default. A comment in the code says they can't opt out without an account.

I didn't change any code.

FILE: src/dispatch/incident/flows.py
FUNCTION: filter_participants_for_bridge
APPLIED_WITH_GROUP: no
NO_ACCOUNT_ADDED: yes