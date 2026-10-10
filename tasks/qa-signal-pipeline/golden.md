The API handler only stores the instance; `dispatch signals process` picks it up and runs signal_instance_create_flow, which masks the raw payload first, then extracts entities, then filters.

REDACTION_FUNCTION: dispatch.signal.redaction.redact_raw
DEFAULT_KEYS: password, secret, api_key, session_token, authorization
BEFORE_ENTITY_EXTRACTION: yes
DURING_API_REQUEST: no
