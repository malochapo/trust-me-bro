The `deduplicate` → `merge` rename is done across the backend, web UI, and tests, and an Alembic migration rewrites the stored values. `python -m pytest tests/signal` passes (32 passed, 1 skipped). The full suite has 8 failures in `tests/ai`, `tests/database`, and `tests/entity`. The same 8 fail on the untouched tree, so they are not from this change.

**What changed**
- **Enum:** `SignalFilterAction.deduplicate = "deduplicate"` is now `merge = "merge"` in `src/dispatch/signal/models.py`.
- **Backend:** the uses in `signal/service.py` and `signal/flows.py` now reference `merge`. The comment in `flows.py` that said "deduplicated" now says "merged".
- **Factory:** `tests/factories.py` picks `"merge"` as the action.
- **Tests:** `tests/signal/test_signal_service.py` uses the new value, and the test function names and comments say "merge" instead of "deduplicate".
- **Web UI:** the radio in `SignalFilterCreateDialog.vue` is now labelled "Merge" with value `merge`. The status chip keys in `TableInstanceTriggers.vue` are renamed, but its display text "Duplicate" is unchanged.
- **Migration:** `src/dispatch/database/revisions/tenant/versions/2026-10-10_3c7a9e1f5b2d.py`, revising `ff08d822ef2c` (the current tenant head). `upgrade()` rewrites `signal_filter.action` and `signal_instance.filter_action` from `'deduplicate'` to `'merge'`. `downgrade()` reverses it. Both columns are plain strings, so no enum type change is needed.
- **OpenAPI:** `docs/scripts/openapi.yaml` lists `merge` in the `SignalFilterAction` enum.

A case-insensitive grep of `src/dispatch` finds the word only in the new migration file, which is allowed.

**Decisions to check**
- The UI label changed from "Deduplicate" to "Merge" to match the new name. If you want the old wording kept, it's a one-line change.
- I left the user-facing docs in `docs/docs/administration/settings/signal/filter.mdx` alone. They still say "deduplicate" because the request was scoped to `src/dispatch`.

**Not verified**
- The migration SQL has not been run against a live tenant schema. Only the test suite was run, and it creates tables from the models rather than through Alembic. Running `alembic upgrade` on a scratch tenant schema would confirm it.