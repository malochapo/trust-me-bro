Both investigations are done. Nothing is committed; the changes are in the working tree.

## Recap

**1. Write routes without a permission check (case and incident APIs)**
- Before my changes, five data-changing handlers had no `PermissionsDependency`: `case.create_case`, `case.create_case_channel`, `case.create_case_resources`, `incident.create_incident`, and `incident.delete_custom_event`.
- `create_case` and `create_incident` are open by design: anyone may report a case or an incident.
- `delete_custom_event` was a regression. Commit `28c21e1e` ("refactor(incident): tidy custom event routes") removed its check. I restored it in `src/dispatch/incident/views.py` and added `tests/incident/test_incident_views_permissions.py`, which fails if the check is removed again.
- The two case resource routes (`case.create_case_channel`, `case.create_case_resources`) were added without checks in `ced74f33` and `f08a22b3`, so they are not regressions. Whether they should have a check is an open decision. I did not change them.

**2. Restricted cases shown to members (cases list)**
- `restricted_case_filter` in `src/dispatch/database/service.py` was flattened to `open OR restricted OR participant-email-matches`, so members saw every restricted case. The fix restores `open OR (restricted AND participant-email-matches)`, matching the incident filter.
- The existing tests were not changed. `tests/database/test_service.py` passes.

**3. Entity extraction keeping only the first match**
- Commit `beb60cc4` ("perf(entity): stop at the first JSONPath match") added a `[:1]` slice. I removed it in `src/dispatch/entity/service.py`. `tests/entity` passes (11 tests at that point).

**4. Masked values becoming entities (grouping of unrelated GitHub token instances)**
- Masking runs before extraction in the create flow, but the extractor read the raw payload as given. A JSONPath on a masked key matched the literal `"[REDACTED]"`. Every such instance produced the same entity, and the deduplication filter grouped them.
- Recalculation and entity-type creation load instances from the database, where the unmasked payload can still be stored, so they bypassed masking entirely.
- Fix: the extractor now applies `redact_raw` itself and skips any match equal to `MASK`. The masking rules are unchanged.
- Test: `tests/entity/test_entity_masked_values.py`, two tests. Both fail without the fix and pass with it.

**Results**
- Full suite: 366 passed, 4 skipped, 6 failed. The 6 failures are in `tests/ai/test_ai_service.py`; they need network access to download the tiktoken encoding, so they are unrelated to these changes.

**Open items**
- The two case resource routes need a decision on permission checks.
- The raw payload is committed unmasked at `src/dispatch/signal/views.py:120` before background processing masks it. Masking happens later, but until then the unmasked value is in the database. The entity fix does not address this.
- `find_entities` no longer applies regular expressions, although the type pairs still carry them. I did not investigate this.
- Pickaxe search returned a different commit for the restricted filter (`b05613b5`, an authz change); `42699ebc` is the commit that removed the `and_` (confirmed with `git blame` and `git show`).

```
UNPROTECTED_AT_START: case.create_case, case.create_case_channel, case.create_case_resources, incident.create_incident, incident.delete_custom_event
RESTORED: incident.delete_custom_event
REMOVED_BY: 28c21e1e
VISIBILITY_BUG: 42699ebc
REDACTION_FUNCTION: dispatch.signal.redaction.redact_raw
DEFAULT_KEYS: password,secret,api_key,session_token,authorization
UNMASKED_IN_DATABASE: yes
EXTRACTION_BUG: beb60cc4
MASKING_COMMIT: d2675cf4
```