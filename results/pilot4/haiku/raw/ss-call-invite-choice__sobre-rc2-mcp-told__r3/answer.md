The function is `filter_participants_for_bridge`, in `src/dispatch/incident/flows.py`. It checks each person's `auto_add_to_incident_bridges` setting and drops anyone who has opted out. It is called from the incident-creation flow at `flows.py:257`, and only on the branch where the incident has no tactical group.

- **Group e-mail:** The choice is not honoured. When the incident has a tactical group, `flows.py:253-254` passes only the group's e-mail address to the conference plugin. The filter is never called, so opted-out responders are added through the group.
- **No Dispatch account:** Yes, they are added. The function keeps any address that has no matching user, with the comment "they can't opt out without a user account" (`flows.py:79-81`).

I did not change any code. I also saved this as a finding in sobre.

FILE: src/dispatch/incident/flows.py
FUNCTION: filter_participants_for_bridge
APPLIED_WITH_GROUP: no
NO_ACCOUNT_ADDED: yes