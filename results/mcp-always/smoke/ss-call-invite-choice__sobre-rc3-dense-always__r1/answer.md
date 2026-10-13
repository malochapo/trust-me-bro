The function that honours the choice is `filter_participants_for_bridge`, in `src/dispatch/incident/flows.py:63`. It is called from `incident_create_resources` (`src/dispatch/incident/flows.py:257`) when the incident has no tactical group. For each participant email it looks up the Dispatch user and keeps the address only if `user_settings.auto_add_to_incident_bridges` is true.

- **Group e-mail:** The choice is not honoured. If `incident.tactical_group` exists, the call is created with the group's e-mail address as the only participant (`flows.py:253-254`), and `filter_participants_for_bridge` is never called. Members of that group are therefore added regardless of their setting.
- **No Dispatch account:** Those people are added. If no user matches the e-mail, the function keeps the address, with the comment "they can't opt out without a user account" (`flows.py:79-81`).

I did not check how `tactical_participant_emails` is built, so I have not verified who is in that list in the first place.

FILE: src/dispatch/incident/flows.py
FUNCTION: filter_participants_for_bridge
APPLIED_WITH_GROUP: no
NO_ACCOUNT_ADDED: yes