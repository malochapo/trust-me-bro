The function that honours the opt-out is `filter_participants_for_bridge`, in `src/dispatch/incident/flows.py:63`. It keeps a participant's email only if that person's user settings have `auto_add_to_incident_bridges` enabled. It is called from `incident_create_resources` (`src/dispatch/incident/flows.py:257`), which passes the result to `conference_flows.create_conference`.

It is not honoured when the incident has a group e-mail address for its responders. In `incident_create_resources`, if `incident.tactical_group` exists, the code sets the conference participants to `[incident.tactical_group.email]` (lines 253–254) and never calls the filter. The call then goes to the group address, and the group plugin's membership decides who is on it. Whether an opted-out responder is excluded therefore depends on whether they are in that group. The code I read does not remove them, so the opt-out has no effect on that path. I did not check the group plugin's membership logic, so that last point is an inference from this code.

People without a Dispatch account are added. `filter_participants_for_bridge` has no account to check their preference, so it keeps them (lines 79–81, with the comment "they can't opt out without a user account").

I did not change any code.

FILE: src/dispatch/incident/flows.py
FUNCTION: filter_participants_for_bridge
APPLIED_WITH_GROUP: no
NO_ACCOUNT_ADDED: yes