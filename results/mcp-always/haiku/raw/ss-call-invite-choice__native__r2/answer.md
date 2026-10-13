The function that honours the choice is `filter_participants_for_bridge`, in `src/dispatch/incident/flows.py`. It checks each person's `auto_add_to_incident_bridges` setting (the default is on) before the conference is created. I didn't change any code.

- **Group e-mail case:** the choice is not honoured. In the conference setup (`src/dispatch/incident/flows.py`, around lines 254–262), if the incident has a `tactical_group`, the conference participants are set to just that group's e-mail address. `filter_participants_for_bridge` is only called in the `else` branch, so each responder's opt-out is skipped and the group address is added instead.
- **No Dispatch account:** those people are added. The function's `else` branch keeps any e-mail that has no matching user, with the comment "they can't opt out without a user account".

FILE: src/dispatch/incident/flows.py
FUNCTION: filter_participants_for_bridge
APPLIED_WITH_GROUP: no
NO_ACCOUNT_ADDED: yes