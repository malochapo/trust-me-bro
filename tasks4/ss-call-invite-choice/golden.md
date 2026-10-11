incident_create_resources creates the conference with [incident.tactical_group.email] when the incident has a tactical group, and only otherwise passes the tactical participants through filter_participants_for_bridge, which keeps a person only if their user settings have auto_add_to_incident_bridges, and keeps every e-mail that has no DispatchUser.

FILE: src/dispatch/incident/flows.py
FUNCTION: filter_participants_for_bridge
APPLIED_WITH_GROUP: no
NO_ACCOUNT_ADDED: yes
