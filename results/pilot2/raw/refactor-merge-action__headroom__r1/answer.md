I renamed the `deduplicate` filter action to `merge` across the backend, the web UI and the tests. I added a migration that rewrites the stored values. The signal tests pass (32 passed, 1 skipped), but I did not run the migration against a database or run the full suite.

- **Backend:** `SignalFilterAction.deduplicate` is now `merge = "merge"` in `src/dispatch/signal/models.py`, and `service.py` and `flows.py` use the new name. I also reworded one comment in `flows.py` that said "deduplicated".
- **Web UI:** `TableInstanceTriggers.vue` and `SignalFilterCreateDialog.vue` now use `merge`. The create dialog's radio label changed from "Deduplicate" to "Merge". I left the instance table's "Duplicate" badge text alone.
- **Migration:** `src/dispatch/database/revisions/tenant/versions/2025-09-02_3c1d7a9e5b42.py` follows the current head `ff08d822ef2c`. It sets `signal_filter.action` and `signal_instance.filter_action` from `deduplicate` to `merge`. The downgrade reverses that.
- **Tests:** `tests/factories.py` and `tests/signal/test_signal_service.py` now use the new name, including test function names and comments.

A case-insensitive search of `src` for `deduplicate` now finds nothing outside the migrations folder.