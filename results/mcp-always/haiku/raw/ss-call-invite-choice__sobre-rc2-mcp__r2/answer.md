The opt-out is honoured by `filter_participants_for_bridge`, but only when the incident has no tactical group e-mail. It is not applied when a group exists.

- **Where the choice is stored:** each user's `auto_add_to_incident_bridges` setting (`src/dispatch/auth/models.py:142`, default `True`).
- **Where it is applied:** `filter_participants_for_bridge` in `src/dispatch/incident/flows.py:65-82` drops an e-mail only when it belongs to a Dispatch user whose setting is off.
- **When the call is created:** in `src/dispatch/incident/flows.py:245-260`, if `incident.tactical_group` exists, the conference is created with only the group's e-mail address and the filter is never called. Otherwise the filter runs on the tactical participant e-mails. So with a group, the opt-out does not stop that person being on the call. The group's membership is also built from the unfiltered list (`tactical_participant_emails`, line 206), so the opt-out is not applied there either. I did not trace how the group e-mail's membership is synced to the call provider, so I can't say whether it could be reversed at that level.
- **People without accounts:** the filter keeps any e-mail that has no Dispatch user, with the comment "they can't opt out without a user account". They are added to the call (in the no-group path).

FILE: src/dispatch/incident/flows.py
FUNCTION: filter_participants_for_bridge
APPLIED_WITH_GROUP: no
NO_ACCOUNT_ADDED: yes