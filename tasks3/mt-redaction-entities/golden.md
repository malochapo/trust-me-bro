Recap. The API handler stores the instance as received; the signal processing loop later runs signal_instance_create_flow, which masks the payload with redact_raw before extracting entities and filtering. Entity extraction kept only the first JSONPath match since a performance change; it keeps every match again. Every masked token became the same "[REDACTED]" entity, which the deduplication filter matched across unrelated instances; masked values are no longer extracted.

REDACTION_FUNCTION: dispatch.signal.redaction.redact_raw
DEFAULT_KEYS: password, secret, api_key, session_token, authorization
UNMASKED_IN_DATABASE: yes
EXTRACTION_BUG: {plant:q3-entity-first-match}
MASKING_COMMIT: {plant:p2-redact-raw}
