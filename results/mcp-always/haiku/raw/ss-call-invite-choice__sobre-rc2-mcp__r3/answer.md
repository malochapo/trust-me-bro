The function that applies the opt-out is `filter_participants_for_bridge`, in `src/dispatch/incident/flows.py`. It checks each participant's `auto_add_to_incident_bridges` setting and drops anyone who has turned it off. `incident_create_resources` (same file, line 179) calls it when it creates the conference room.

- **With a group e-mail address:** The choice is not honoured. When the incident has a `tactical_group`, `incident_create_resources` passes only that group's e-mail to `create_conference` and never calls the filter (lines 252–259). Opted-out responders are added through the group's membership instead.
- **Without a Dispatch account:** Those people are added. The filter's `else` branch keeps any e-mail that has no matching user, with the comment "they can't opt out without a user account."

FILE: src/dispatch/incident/flows.py
FUNCTION: filter_participants_for_bridge
APPLIED_WITH_GROUP: no
NO_ACCOUNT_ADDED: no