The opt-out is honoured by `filter_participants_for_bridge`, but only when the incident has no tactical group e-mail. With a group address, the opt-out is ignored. People without a Dispatch account are added to the call.

- **Function that honours the choice:** `filter_participants_for_bridge` (`src/dispatch/incident/flows.py:63-82`). It keeps an e-mail only if the matching Dispatch user has `auto_add_to_incident_bridges` set. The setting is defined in `src/dispatch/auth/models.py:142` and defaults to `True`.
- **Caller:** `incident_create_resources` (`src/dispatch/incident/flows.py:248-262`) builds the conference participants. The filter runs only in the `else` branch, i.e. when `incident.tactical_group` is unset. When a tactical group exists, the call is created with just `[incident.tactical_group.email]`, so individual preferences are never read.
- **No account:** the filter's `else` branch (`flows.py:79-81`) keeps any e-mail that has no Dispatch user, with the comment that such people "can't opt out without a user account".

I did not change any code.

FILE: src/dispatch/incident/flows.py
FUNCTION: filter_participants_for_bridge
APPLIED_WITH_GROUP: no
NO_ACCOUNT_ADDED: yes