## Recap

**Flow.** `POST /api/v1/{organization}/signals/instances` is handled by `create_signal_instance` in `signal/views.py`. The view resolves the project and signal definition, then calls `create_instance` in `signal/service.py`, which stores the payload in the `raw` JSONB column. The view then commits and returns. Nothing is masked at this stage.

A scheduler or CLI loop later picks up instances with no `filter_action` and no case, and runs `signal_instance_create_flow`. That flow does the following:
1. Masks `raw`.
2. Extracts entities and commits.
3. Applies snooze and dedup filters. A filtered instance stops there, possibly after updating the Slack message.
4. Skips case creation for canary signals and for signals with `create_case=False`.
5. Otherwise creates the case.

**Masking.** `redact_raw` replaces the value of any matching key with `"[REDACTED]"`. Keys match exactly and case-insensitively, at any depth. The default list is set in `config.py` and can be overridden with the `SIGNAL_REDACTED_RAW_FIELDS` env var.

**Unmasked data in the database.** The view commits the unmasked payload before the flow runs. The cleartext stays in the column until the flow's next commit overwrites it, which is at least one scheduler cycle (about 60 s). It is longer if the flow errors and rolls back. Backups, WAL and replicas taken in that window can retain it. The POST response also returns the unmasked `raw`.

**Bug 1, only the first match was kept.** Commit `beb60cc4` added `[:1]` to the JSONPath results, so extraction lost all but the first match. I reverted that line, and the change is uncommitted.

**Bug 2, masked values grouped unrelated cases.** After masking, a JSONPath pointing at a masked field yielded the entity `[REDACTED]`. All instances then shared that one entity, and the dedup filter grouped them. Extraction now skips any value equal to the mask, and a new test covers it. The change is uncommitted.

**Open items.**
- Mask on write, in `create_instance` or the view, to close the cleartext window.
- Widen the default key list. Names such as `client_secret`, `apiKey` and `access_token` are not covered.
- Clean up the existing shared `[REDACTED]` entity rows.

REDACTION_FUNCTION: dispatch.signal.redaction.redact_raw
DEFAULT_KEYS: password,secret,api_key,session_token,authorization
UNMASKED_IN_DATABASE: yes
EXTRACTION_BUG: beb60cc4
MASKING_COMMIT: d2675cf4