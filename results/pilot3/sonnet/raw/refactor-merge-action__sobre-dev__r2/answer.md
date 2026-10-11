The signal filter action `deduplicate` is now `merge` throughout the backend and web UI, and the stored values are migrated. `python -m pytest tests/signal` gives 32 passed, 1 skipped. I did not run the full suite, and I did not run the migration against a database.

- **Backend:** `SignalFilterAction.merge = "merge"` replaces the old member, and the uses in `signal/service.py` and `signal/flows.py` follow. The comments in those files that said "deduplication" or "deduplicated" now say "merge" or "merged".
- **Web UI:**
  - The create dialog's radio is now `Merge` with value `merge`.
  - The conditional check on that value is updated.
  - `TableInstanceTriggers.vue` has the renamed color and label key.
  - Two text strings in `NewEditDialog.vue` and `store.js` are reworded.
- **Migration:** `2025-09-02_a3c1e5d7b9f2.py` in the tenant revisions, revising `ff08d822ef2c`, which was the head. It updates `signal_filter.action` and `signal_instance.filter_action` from `deduplicate` to `merge`, and the downgrade reverses that.
- **Tests:** `tests/signal/test_signal_service.py` and `tests/factories.py` use the new name.
- **Outside the request:** I also updated `docs/scripts/openapi.yaml` and `docs/docs/administration/settings/signal/filter.mdx`, since they carried the old name.

A search for `deduplicat` in `src/dispatch` finds it only in the migration.

I left the instance table's display label as "Duplicate", since you asked for no behavior change. Say if you want it to read "Merge".