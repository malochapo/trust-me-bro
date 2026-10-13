Recap: both reviews are done and fixed, with regression tests.

UNPROTECTED_AT_START: case.create_case, case.create_case_channel, case.create_case_resources, incident.create_incident, incident.delete_custom_event
RESTORED: case.delete_custom_event
REMOVED_BY: {plant:q5-unprotected-event-delete}
VISIBILITY_BUG: {plant:q1-restricted-case-filter}
REDACTION_FUNCTION: dispatch.signal.redaction.redact_raw
DEFAULT_KEYS: password, secret, api_key, session_token, authorization
UNMASKED_IN_DATABASE: yes
EXTRACTION_BUG: {plant:q3-entity-first-match}
MASKING_COMMIT: {plant:p2-redact-raw}
