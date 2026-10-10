I renamed `deduplicate` to `merge` across the backend, web UI and tests, and added a migration for the stored values. The signal tests pass (32 passed, 1 skipped). I didn't run the rest of the suite or the migration itself.

- **Backend:** `SignalFilterAction.merge = "merge"` replaces the old member, and the uses in `signal/service.py` and `signal/flows.py` are updated.
- **Web UI:** the filter create dialog now sends `value="merge"` and compares against `'merge'`. The instance table's color and label maps are keyed on `merge`.
- **Migration:** `2025-09-02_3b1c7e5a9d42.py` follows `ff08d822ef2c`, the previous head. It updates `signal_filter.action` and `signal_instance.filter_action` from `deduplicate` to `merge`, and the downgrade reverses that.
- **Tests:** the factory choices and `tests/signal/test_signal_service.py` use the new name, including the renamed test functions.

`grep` finds no `deduplicate` left in `src/dispatch` outside the migrations. The related words "deduplication" and "deduplications" still appear in a few comments and in two UI strings, in `signal/NewEditDialog.vue` and `signal/instance/store.js`. I left them alone because they aren't the word you named.

I also kept the "Duplicate" display label for the action in the instance table, and "Deduplicate" in the create dialog now reads "Merge". Say so if you want the table label changed too.