The function that honours the opt-out is `filter_participants_for_bridge`. It is called from `create_incident_flow` and checks each responder's `auto_add_to_incident_bridges` user setting. That setting defaults to `True`, so people are included unless they have switched it off.

**Group e-mail case:** the choice is not honoured. When the incident has a tactical group, `create_incident_flow` sets the conference participants to just `[incident.tactical_group.email]` and never calls the filter. The opt-out has no effect on the call. Whether the group address adds the person to the call depends on the group's membership and the conference plugin, which this code does not control.

**No-account case:** people without a Dispatch account are added. The filter keeps any e-mail that has no matching user, and the code comment says they cannot opt out without an account. This only applies when there is no tactical group, because the group path skips the filter entirely.

Relevant locations (no code changed):
- `src/dispatch/incident/flows.py:63-82` defines `filter_participants_for_bridge`.
- `src/dispatch/incident/flows.py:248-261` builds the conference participant list and calls it, or bypasses it when a tactical group exists.
- `src/dispatch/auth/models.py:142` defines the `auto_add_to_incident_bridges` column.
- `src/dispatch/conference/flows.py:14` `create_conference` passes the list to the conference plugin.

FILE: src/dispatch/incident/flows.py
FUNCTION: filter_participants_for_bridge
APPLIED_WITH_GROUP: no
NO_ACCOUNT_ADDED: yes