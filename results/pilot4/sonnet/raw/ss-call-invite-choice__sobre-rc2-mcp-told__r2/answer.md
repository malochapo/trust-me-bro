The function that honours the choice is `filter_participants_for_bridge`. It reads each person's `auto_add_to_incident_bridges` setting, which defaults to true.

**Where it is called.** The incident flow calls it when it creates the conference, at `src/dispatch/incident/flows.py:248-261`. It runs only if the incident has no conference yet.

**When the incident has a group e-mail address.** The choice is not honoured. If `incident.tactical_group` exists, the call's participant list is just `[incident.tactical_group.email]`. The filter is never called, so the group address goes straight to the conference. The filter only runs in the `else` branch, when there is no tactical group. In the group case, individuals' opt-outs have no effect on the call, though membership of the group itself is decided elsewhere.

**People without a Dispatch account.** They are added. The filter looks each e-mail up with `auth_service.get_by_email`. If no user is found, it appends the e-mail anyway. A comment in the code says these people cannot opt out because they have no account.

FILE: src/dispatch/incident/flows.py
FUNCTION: filter_participants_for_bridge
APPLIED_WITH_GROUP: no
NO_ACCOUNT_ADDED: yes