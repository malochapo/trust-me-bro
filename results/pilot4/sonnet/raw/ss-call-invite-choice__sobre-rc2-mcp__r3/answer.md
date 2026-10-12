I've found the function and have what I need to answer.

**Which function honours the choice:** `filter_participants_for_bridge` in `src/dispatch/incident/flows.py:63`. For each responder e-mail it looks up the Dispatch user and reads their settings. It keeps the person only if `auto_add_to_incident_bridges` is true. The incident setup code calls it just before `conference_flows.create_conference`, and passes the filtered list as the call's participants.

**Group e-mail address:** No, the choice isn't honoured in that case. In the conference step of the incident setup (`flows.py` ~L252–258), if `incident.tactical_group` exists, the participant list is just `[incident.tactical_group.email]`. The filter is only called in the `else` branch. The call is therefore set up for the group address, and each member's opt-out is ignored.

**People without a Dispatch account:** Yes, they are added. When `auth_service.get_by_email` finds no user, the function appends the e-mail anyway. A comment in the code says these people can't opt out without an account.

FILE: src/dispatch/incident/flows.py
FUNCTION: filter_participants_for_bridge
APPLIED_WITH_GROUP: no
NO_ACCOUNT_ADDED: yes