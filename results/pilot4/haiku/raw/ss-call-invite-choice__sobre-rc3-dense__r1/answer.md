The function is `filter_participants_for_bridge`, in `src/dispatch/incident/flows.py:63`. It is called from `incident_create_resources` (line 257), which sets up the conference room when an incident is created. It checks each participant's `auto_add_to_incident_bridges` user setting, which defaults to `True`, and drops anyone who has turned it off.

**With a group e-mail address:** the choice is not honoured. The filter runs only in the `else` branch, when the incident has no tactical group. If there is a tactical group, the conference is created with just the group's e-mail address (`flows.py:254-260`). Nobody is filtered, so opted-out responders are still pulled into the call through the group. The opt-out is also not applied when the tactical group's membership is built, since that uses the unfiltered `tactical_participant_emails` (`flows.py:211-216`).

**People without a Dispatch account:** yes, they are added. For an address with no matching user, the filter's `else` branch keeps the address (`flows.py:80-83`), with the comment "they can't opt out without a user account".

FILE: src/dispatch/incident/flows.py
FUNCTION: filter_participants_for_bridge
APPLIED_WITH_GROUP: no
NO_ACCOUNT_ADDED: yes