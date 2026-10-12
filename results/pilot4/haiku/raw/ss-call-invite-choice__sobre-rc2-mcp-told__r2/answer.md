The opt-out is honoured by `filter_participants_for_bridge`, but only when the incident has no tactical group e-mail. With a group address, the opt-out is bypassed. People without a Dispatch account are always added. I changed no code.

- **Opt-out function:** `filter_participants_for_bridge` (`src/dispatch/incident/flows.py:63`) checks each participant's `auto_add_to_incident_bridges` setting and keeps only those who have it enabled.
- **Where it runs:** `incident_create_resources` (`src/dispatch/incident/flows.py:257`) calls it when the conference is created. The call is made only in the `else` branch, so it runs only when `incident.tactical_group` is unset.
- **With a group e-mail:** if `incident.tactical_group` is set, the conference is created with just the group's e-mail address (`flows.py:254-259`). The per-user filter is never called, so the opt-out has no effect.
- **No account:** the filter keeps any e-mail that has no matching Dispatch user, with the comment "they can't opt out without a user account". Those people are added.

I also saved this as a finding in the sobre session.

FILE: src/dispatch/incident/flows.py
FUNCTION: filter_participants_for_bridge
APPLIED_WITH_GROUP: no
NO_ACCOUNT_ADDED: yes