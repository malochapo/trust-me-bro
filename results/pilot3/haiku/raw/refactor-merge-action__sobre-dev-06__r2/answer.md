The `deduplicate` action is now `merge` throughout `src/dispatch`, and a tenant migration rewrites the stored values. The signal test suite passes (32 passed, 1 skipped). A grep of `src/dispatch` outside the migrations finds no remaining `deduplicate`.

**Changes**
- **Enum:** `SignalFilterAction.deduplicate = "deduplicate"` is now `merge = "merge"` in `src/dispatch/signal/models.py`.
- **Backend:** `service.py` and `flows.py` use `SignalFilterAction.merge`. I also reworded comments that said "deduplicated" to "merged". Behavior is unchanged.
- **Web UI:** `SignalFilterCreateDialog.vue` has the radio value `merge`, the label "Merge", and the conditional on `merge`. `TableInstanceTriggers.vue` maps `merge` to the same color as before.
- **Tests:** `tests/factories.py` and `tests/signal/test_signal_service.py` use the new name, including renamed test functions.
- **Migration:** `src/dispatch/database/revisions/tenant/versions/2026-10-10_407732dbb07e.py` chains onto the current head `ff08d822ef2c`. Upgrade sets `signal_filter.action` and `signal_instance.filter_action` from `'deduplicate'` to `'merge'`. Downgrade reverses it. Both columns are plain strings, so no native enum type needs altering.

**Choices you may want to review**
- The UI chip text "Duplicate" in `TableInstanceTriggers.vue` is unchanged. It is a display label, not the action name. The radio button label changed to "Merge" to match the action.
- `docs/scripts/openapi.yaml` had the enum value, so I updated it too. That file is outside `src/dispatch`.
- `docs/docs/administration/settings/signal/filter.mdx` still says "deduplicate" in prose ("Deduplication Filter"). I left the user docs alone; say if you want them updated.

**Not verified**
- I did not run the migration against a database. No test exercises the migrations, and the SQL is two `UPDATE` statements per direction.
- ruff is not installed here, so I did not run lint or format checks on the changed Python files.
- I did not run the full test suite beyond `tests/signal`.