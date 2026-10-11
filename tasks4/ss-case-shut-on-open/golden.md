case_new_create_flow calls case_auto_close_flow when the case type has auto_close set; it sets the resolution to 'Auto closed via case type auto close configuration.', the resolution reason to CaseResolutionReason.user_acknowledged and the status to closed, then runs the triage and closed status flows.

FILE: src/dispatch/case/flows.py
FUNCTION: case_auto_close_flow
REASON: User Acknowledged
