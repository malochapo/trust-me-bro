The unmasked payload is written to the database. Masking only happens afterwards, in a separate asynchronous step. I traced this by reading the code, and I haven't run anything or changed any code.

## Trace

1. **API view**, `signal/views.py:72`, `create_signal_instance` (POST `/instances`):
   - It resolves the project and the signal definition (by `externalId`/`variant`, then the default definition, otherwise 404).
   - It calls `signal_service.create_instance(...)` and then `db_session.commit()`. A duplicate id gives a 409.
   - It returns the instance without running any case or filter logic. `background_tasks` is injected but never used.
2. **`signal/service.py:650`, `create_instance`**:
   - It copies `signal_instance_in.raw`, and round-trips it through `json.loads(json.dumps(...))` to turn dates into strings.
   - It builds the `SignalInstance` with `raw=` set to that copy, uses `raw["id"]` as the primary key if one is present, validates it as a UUID, and calls `db_session.add`.
   - **There is no masking here.**
3. **Asynchronous processing**:
   - `get_unprocessed_signal_instance_ids` (`signal/service.py:900`) picks instances with `filter_action IS NULL` and `case_id IS NULL`. The scheduler path is `process_organization_signals` → `process_signal_batch` in `signal/flows.py`, and `cli.py:~1004` has a similar loop.
   - Each one runs `signal_instance_create_flow` (`signal/flows.py:46`), which does the following in order:
     - **Masking:** `signal_instance.raw = redact_raw(signal_instance.raw)` (`flows.py:60`).
     - **Entities:** entity extraction through `entity_service.find_entities`, which runs JSONPath over the now-masked `raw` (`entity/service.py:290`). Then `db_session.commit()`.
     - **Filtering:** `signal_service.filter_signal` (`service.py:866`) applies snooze, then dedup. It commits and sets `filter_action`, with `none` meaning not filtered.
     - **Filtered out:** if the instance was snoozed or deduplicated, the flow returns early. If the instance is attached to a case that has a conversation, it may update the Slack signal message.
     - **Stored only:** canary signals, and signals with `create_case=False`, are stored and returned without opening a case.
     - **Case creation:** otherwise the flow resolves case type and priority and creates the case. It also handles engagements and workflows.

## Masking details

- **Function:** `redact_raw` in `src/dispatch/signal/redaction.py`, which calls the recursive helper `_redact`. It was added in commit `d2675cf4`.
- **Behaviour:**
  - It returns a copy.
  - Keys match case-insensitively, at any depth, inside dicts and lists.
  - A matching key's value becomes `"[REDACTED]"`.
  - Non-dict and non-list values are returned unchanged.
  - Only keys are checked. Sensitive values under other key names, or inside strings, are not touched.
- **Default keys:** `password, secret, api_key, session_token, authorization`. These come from `SIGNAL_REDACTED_RAW_FIELDS` in `config.py:98`, which can be overridden by an env var of the same name (comma-separated).
- **Matching is exact, not substring.** `client_secret`, `apiKey` and `access_token` are not masked by default.

## Is the unmasked payload written to the database?

Yes. The view's `commit()` persists the raw payload before any redaction. The cleartext stays in the `signal_instance.raw` JSONB column until the background flow runs and its next commit overwrites the column.

- **Window:** The cleartext exists from the POST until the next scheduler pass, which loops with a `LOOP_DELAY` of 60 seconds. It can be longer if the flow errors, because `process_signal_batch` rolls back and the instance is retried.
- **Backups:** Database backups, WAL and replicas taken in that window can keep the cleartext after the column is overwritten.
- **Returned to the client:** The POST response is `SignalInstanceRead`, which includes `raw`. It is serialized from the unmasked object, so the caller gets it back unmasked.
- **Logs:** `create_instance` interpolates `raw['name']` or `raw['variant']` into error messages, and the view logs `raw.get('id')` and `raw.get('variant')`. These are not sensitive keys by default.

## Other issues noticed

- **`signal_definition` bug:** In `views.py`, `signal_definition` is only assigned inside `if not signal_instance_in.signal:`. If the client supplies a `signal`, the next `if not signal_definition:` raises `UnboundLocalError`. `external_id` and `variant` have the same problem in the log messages.
- **Escaped log format:** `flows.py:55` has `"%%s"` in `log.error`, which logs a literal `%s`.

## Fix options

- **Redact on write:** Call `redact_raw` in `create_instance`, or in the view before storing. This closes the gap and still lets entity extraction see masked data. The catch is that anything needing the original values later, such as the plugin payload, would no longer have them.
- **Wider default keys:** Extend the default key list, for example with `token`, `client_secret` or `access_token`.

I haven't made either change. Tell me if you want one.

----- next turn -----

Entity extraction now returns every JSONPath match again, and the `tests/entity` suite passes (11 tests).

The cause was commit `beb60cc4`, "perf(entity): stop at the first JSONPath match". It changed `jpath.find(signal_instance.raw)` to `jpath.find(signal_instance.raw)[:1]` in `_find_entities_by_jsonpath_expression` (`src/dispatch/entity/service.py`). Any expression matching several fields, such as `$.users[*].email` or a recursive `$..ip`, then produced only one entity.

I reverted that line, so the code is back to `matches = jpath.find(signal_instance.raw)`, and left the tests alone. The change is not committed.

The commit was meant as a performance tweak, but `find` already computes every match before the slice. The slice saved nothing and dropped data. If you want it faster, a lazy approach would have to stop the search early, and that would conflict with the multi-match behavior the tests expect.

I only ran `tests/entity`, not the full suite.

----- next turn -----

Masked values no longer become entities, and the new test passes along with the rest of `tests/entity` and `tests/signal` (44 passed, 1 skipped).

**Why unrelated instances were grouped:** `signal_instance_create_flow` runs `redact_raw` before it extracts entities (`flows.py:60`). The `session_token` value becomes the literal string `"[REDACTED]"`. The entity type's JSONPath then matches that string. Every instance of the signal ends up with an entity whose value is `[REDACTED]`. `get_by_value_or_create` reuses a single shared entity for that value, and the deduplication filter on that entity type groups everything that has it, whatever the real token was.

**Fix:** In `src/dispatch/entity/service.py`, `_find_entities_by_jsonpath_expression` now skips any match whose value equals `MASK`, imported from `dispatch.signal.redaction`. That is the only place entities are extracted from a payload: `find_entities` is the sole entry point, and nothing else builds an `EntityCreate`. The masking itself is unchanged.

**Test:** I added `test_find_entities_skips_masked_values` to `tests/entity/test_entity_service.py`. It redacts a payload containing `session_token` and a nested `Password`, then checks that JSONPaths pointing at those fields produce no entities. A path to an unmasked field, `asset[*].id`, still produces its entity. I didn't change any existing tests.

**Things to know:**
- **Unrelated diff lines:** `git diff` also still shows the earlier uncommitted revert of the `[:1]` slice in the same file. Nothing is committed.
- **Old data:** Instances already processed keep the shared `[REDACTED]` entity. Existing cases they were grouped into are unaffected by this fix. A cleanup of those entity rows may be needed. I haven't looked at that.
- **Redaction gaps:** Redaction only matches the default keys exactly, so tokens under other key names, such as `access_token`, still become real entities. Those entities are the real token value, so they would group correctly but are stored in cleartext. This is the gap from the first trace.

----- next turn -----

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