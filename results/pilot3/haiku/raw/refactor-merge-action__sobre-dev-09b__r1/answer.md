The rename is done: `SignalFilterAction.deduplicate` is now `SignalFilterAction.merge` with value `"merge"`, and a new tenant migration rewrites stored values. No `deduplicate` remains in `src/dispatch` outside the migrations. The signal tests pass (32 passed, 1 skipped). The full suite has the same 8 failures as before my change (AI service and a few database/entity tests), so none are caused by this change.

**What changed**
- **Backend:** the enum member and value in `signal/models.py`, plus every use in `signal/service.py` and `signal/flows.py`. The comments that said "deduplicated" now say "merged".
- **Web UI:** the filter dialog radio is labelled "Merge" with value `merge`, and the tooltip in `NewEditDialog.vue` says "Merge". The instance table chip colour is keyed on `merge`.
- **Tests:** `tests/factories.py` and `tests/signal/test_signal_service.py` use `merge`. The test function names changed too.
- **Migration:** `src/dispatch/database/revisions/tenant/versions/2026-10-11_8295286c1489.py`, revising the current head `ff08d822ef2c`. Upgrade sets `signal_filter.action` and `signal_instance.filter_action` from `'deduplicate'` to `'merge'`. Downgrade reverses it. Both columns are plain strings, so no Postgres enum type needed altering.
- **Outside `src/dispatch`:** I also updated `docs/scripts/openapi.yaml` (the API enum) and the two filter doc pages, so they match the new name.

**Choices you may want to revisit**
- The instance table still shows the chip text "Duplicate", because that is display text and I did not want to change what users see. Tell me if you want it to read "Merged".
- I left the word "deduplication" alone in comments and docs. It is not the word `deduplicate`, and it names the feature rather than the action.

**Not verified**
- I did not run the migration against a live database. The SQL is two plain `UPDATE` statements, and the file compiles.
- `ruff` is not installed here, so lint and format were not checked.
- `test_filter_actions_merge` is defined twice in `tests/signal/test_signal_service.py`, as `test_filter_actions_deduplicate` was before. The second definition shadows the first, so one of those tests never runs. I left it alone because it predates this change.