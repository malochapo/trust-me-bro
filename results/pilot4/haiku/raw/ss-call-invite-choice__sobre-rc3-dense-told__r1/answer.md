The opt-out is honoured by `filter_participants_for_bridge`, but only when the incident has no responder group e-mail. Nobody without a Dispatch account can opt out, so they are always added.

- **Opt-out check:** `filter_participants_for_bridge` (`src/dispatch/incident/flows.py:63`) looks up each participant's Dispatch user by e-mail and keeps them only if `user_settings.auto_add_to_incident_bridges` is true.
- **Where it runs:** the incident flow calls it at `src/dispatch/incident/flows.py:257` when it creates the conference, then passes the result to `conference_flows.create_conference` (`src/dispatch/conference/flows.py:14`). That function does no filtering of its own.
- **Group e-mail case:** if `incident.tactical_group` is set, the flow passes only `[incident.tactical_group.email]` to the conference and never calls the filter (`src/dispatch/incident/flows.py:253-254`). So the choice is not applied and the group address is invited as a whole.
- **No-account case:** the filter keeps any address with no matching Dispatch user, with the comment that such people "can't opt out without a user account" (`src/dispatch/incident/flows.py:80-82`).

I did not change any code. I also saved this as a finding in the sobre session.

FILE: src/dispatch/incident/flows.py
FUNCTION: filter_participants_for_bridge
APPLIED_WITH_GROUP: no
NO_ACCOUNT_ADDED: yes