**Yes, the unmasked payload is written to the database.** Masking happens later, in a separate worker step, and the POST response also returns the raw payload unmasked. I read the code only and ran nothing.

## Trace

**1. API request.** `create_signal_instance` in `signal/views.py:72` handles the POST.
- It resolves the project.
- It finds the signal definition by `raw.externalId` or `raw.variant`, falling back to the project's default definition, or returns 404 if there is none.
- It calls `signal_service.create_instance` (`signal/service.py:650`), then `db_session.commit()`. A duplicate id returns 409.

**2. Persisting the instance.** `create_instance` copies `signal_instance_in.raw`, drops `oncall_service`, and round-trips it through JSON. It stores the result in `SignalInstance.raw` (a JSONB column, `signal/models.py:239`). There is no masking here. The view's `background_tasks` parameter is never used, so nothing is triggered from the request.

**3. Worker pickup.** A separate process selects instances where `filter_action IS NULL` and `case_id IS NULL`, oldest first, up to 500 per organization. It calls `signal_flows.signal_instance_create_flow` on each and commits per instance. There are two such loops:
- `process_signal_batch` in `signal/flows.py:~380`, which is the one that handles `process_organization_signals`.
- The `cli.py` loop around line 1004.

**4. `signal_instance_create_flow`** (`signal/flows.py:46`):
- **Masking:** `signal_instance.raw = redact_raw(signal_instance.raw)` (line 60). This happens before entity extraction.
- **Entity extraction:** it finds entities with `entity_service.find_entities` and commits, which also flushes the masked `raw`.
- **Filtering:** `signal_service.filter_signal` applies the snooze filter, then the dedup filter. If either sets a filter action, the instance is filtered. The flow then logs it, updates the case's signal message if it was deduplicated into an existing case, and returns.
- **Case creation:** if the instance is not filtered, it stops for canary instances and for signals with `create_case` off. Otherwise it resolves case type, priority, oncall assignee and conversation target, builds a `CaseCreate`, calls `case_service.create`, links `signal_instance.case`, and commits. The rest of the flow runs the case creation and notification steps.

## Masking details

- **Function:** `redact_raw` in `signal/redaction.py:10`, with the recursive helper `_redact`.
- **Behaviour:**
  - It returns a copy in which the value of any matching key is replaced with `"[REDACTED]"`.
  - Matching is case-insensitive, at any depth, and inside dicts and lists.
  - Only values under a matching key are masked. Values that merely look like secrets are not.
- **Default keys:** `password, secret, api_key, session_token, authorization`. They come from `SIGNAL_REDACTED_RAW_FIELDS` in `config.py:98`, which can be overridden by an env var of the same name (comma-separated).
- **Other callers:** `redact_raw` is called only from `signal/flows.py:60`.

## Is the unmasked payload ever written to the database?

Yes, in two ways:
- **Initial commit.** `create_instance` plus the view's `db_session.commit()` store the full raw payload, unredacted. It stays that way until the worker runs the flow. If the worker is down, lagging, or crashes before the commit, the secrets stay in the database. The window is also open to anyone who can read `signal_instance.raw` in the meantime.
- **`update_instance`** (`signal/service.py:726`) overwrites `raw` from the input without redacting. If anything calls it, it can re-store unmasked data after the flow has run. I did not trace its callers.

Related exposures:
- **API response.** The POST returns `SignalInstanceRead`, which includes `raw`. That response is built from the unmasked instance. The GET `/instances` listing returns `raw` as stored, so it is unmasked until the worker has processed the instance.
- **Overwritten secrets.** Once the flow commits, the redacted value replaces the original in the JSONB column, so the secret is overwritten rather than retained. Postgres WAL, backups and any replicas may still hold the earlier version.
- **Redaction failure.** If `redact_raw` raised, the exception would be caught by the batch loop's `except`, which rolls back and logs. Redaction would then retry on later passes, since the instance still has no `filter_action`.
- **Log message.** Separately, `log.error("signal_instance is None for id: %%s", ...)` at `flows.py:55` has a doubled `%%`, so it never interpolates the id.

If you want the secrets never to hit the database, the fix would be to call `redact_raw` in `create_instance` before building `SignalInstance`, and in `update_instance`. I haven't changed anything.

----- next turn -----

Commit `beb60cc4` ("perf(entity): stop at the first JSONPath match") caused it. It changed `find_entities` in `src/dispatch/entity/service.py` to `jpath.find(signal_instance.raw)[:1]`. That truncated every JSONPath to its first match, so an entity type matching several fields produced only one entity.

I restored `matches = jpath.find(signal_instance.raw)` and removed the comment that justified the truncation. No tests were modified. `python -m pytest tests/entity` now gives 11 passed.

The commit's claim that a JSONPath names one field is wrong for wildcard and recursive paths such as `$..ip` or `items[*].host`. If you want the performance gain back, it would have to be a different change, such as caching the compiled path or de-duplicating values, not truncating the results.

I haven't committed the fix.

----- next turn -----

**Cause.** `signal_instance_create_flow` calls `redact_raw` before `find_entities`. For that signal, the JSONPath on the session token therefore matched `"[REDACTED]"` for every instance. That string became one shared `Entity`, and the dedup filter on the entity type grouped all those instances into one case.

**Fix.** All entity extraction goes through `find_entities` in `src/dispatch/entity/service.py`. That covers the signal flow, entity-type creation and update, and the entity-type flow. A match is now skipped in two cases:
- Its value is the mask.
- Its last path key is one of the redacted field names, matched case-insensitively. This also stops real secrets becoming entities when `raw` isn't masked yet, for example when an entity type is created or updated against instances the worker hasn't processed.

The check is a new `is_redacted_match` in `src/dispatch/signal/redaction.py`. `redact_raw` and its defaults are unchanged.

**Test.** `test_find_entities_skips_masked_values` in `tests/entity/test_entity_service.py` covers both the unmasked and the masked payload. `python -m pytest tests/entity tests/signal` gives 44 passed and 1 skipped. I didn't run the rest of the suite, and I haven't committed.

**Limitations.**
- The key check only looks at the last field of the path. A path like `creds[*]` that reaches a secret through a list index, or `$..*`, is not caught by key name. A masked payload is still safe, because the value check catches the mask.
- An instance already grouped by the earlier bug keeps its `[REDACTED]` entity and its case grouping. Old `[REDACTED]` entity rows may need a cleanup.

----- next turn -----

## Recap

**Flow.** `POST /api/v1/{organization}/signals/instances` stores the instance and returns. A separate worker later runs `signal_instance_create_flow`. The flow masks the payload, extracts entities, applies the snooze and dedup filters, and then either stops (filtered, canary, or `create_case` off) or creates a case.

**Masking.** `redact_raw` in `signal/redaction.py` replaces the value of any key matching a configured name with `[REDACTED]`. Matching is case-insensitive, at any depth, and inside lists. It is called only from `signal/flows.py:60`. The defaults come from `SIGNAL_REDACTED_RAW_FIELDS`, which an env var of the same name can override.

**Unmasked in the database.** Yes. The API view and `create_instance` commit the raw payload before the worker masks it. The masked version overwrites it only once the worker's flow commits. The POST response and `GET /instances` also return the unmasked `raw` until then. `update_instance` does no redaction at all.

**Extraction bug.** Commit `beb60cc4` added `[:1]` to the JSONPath results, so only the first match became an entity. I removed it, and the entity tests pass.

**Masked-entity bug.** The flow masks before extracting entities, so a JSONPath pointing at a secret matched `[REDACTED]` for every instance. All those instances shared one entity, and dedup grouped them into one case. `find_entities` now skips masked values and values under redacted keys, with a new test. The `tests/entity` and `tests/signal` suites pass. The fix is uncommitted.

**Still open.**
- Closing the unmasked-at-rest window means calling `redact_raw` in `create_instance` and `update_instance`. I haven't changed that.
- Old `[REDACTED]` entities and the case groupings they caused still need cleanup.
- Paths that reach a secret through a list index are not caught by the key check.

REDACTION_FUNCTION: dispatch.signal.redaction.redact_raw
DEFAULT_KEYS: password,secret,api_key,session_token,authorization
UNMASKED_IN_DATABASE: yes
EXTRACTION_BUG: beb60cc49435f38d6296e1607b07f6dff31804b1
MASKING_COMMIT: d2675cf4b078246ae14df279469af513b348ab95