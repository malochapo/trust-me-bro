The function that honours the choice is `filter_participants_for_bridge`. It's defined in `src/dispatch/incident/flows.py` at line 63. The incident creation flow calls it just before it calls `conference_flows.create_conference`, at about lines 249–261.

**How the choice is applied.** For each responder e-mail, the function looks up the Dispatch user and loads their settings. It keeps the person only if `auto_add_to_incident_bridges` is true. That field is a per-user setting, and it defaults to true.

**With a group e-mail address.** No, the choice isn't honoured in that case. If the incident has a `tactical_group`, the creation flow sets the call's participants to `[incident.tactical_group.email]` and never calls the filter. The group's membership decides who is on the call. The filter only runs when there is no tactical group.

**People without an account.** Yes, they are added. If `auth_service.get_by_email` finds no Dispatch user, the function keeps the e-mail. A code comment gives the reason: they can't opt out without a user account.

FILE: src/dispatch/incident/flows.py
FUNCTION: filter_participants_for_bridge
APPLIED_WITH_GROUP: no
NO_ACCOUNT_ADDED: yes