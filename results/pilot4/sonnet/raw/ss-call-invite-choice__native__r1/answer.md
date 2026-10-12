The function that honours the choice is `filter_participants_for_bridge`, defined at `src/dispatch/incident/flows.py:63`. When an incident's call is set up, the call-creation step in the same file (around lines 248–261) passes the tactical responders' e-mails through it.

- **How it works:** for each e-mail, it looks up the Dispatch user and loads their settings. It keeps the person only if `auto_add_to_incident_bridges` is true. Anyone who has turned that off is dropped from the call.
- **Incident has a group e-mail:** no, the choice is not honoured. If `incident.tactical_group` exists, the participant list is replaced with `[incident.tactical_group.email]` and the filter is never called. Everyone in that group is therefore invited, whatever their setting. The earlier line `conference_participants = tactical_participant_emails` is dead code, because both branches overwrite it.
- **People without a Dispatch account:** yes, they are added. `filter_participants_for_bridge` finds no user for them and keeps them by default. A code comment explains that they can't opt out without an account.

FILE: src/dispatch/incident/flows.py
FUNCTION: filter_participants_for_bridge
APPLIED_WITH_GROUP: no
NO_ACCOUNT_ADDED: yes