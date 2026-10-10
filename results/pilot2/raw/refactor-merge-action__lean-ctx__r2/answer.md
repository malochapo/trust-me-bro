I renamed the `deduplicate` filter action to `merge` throughout the code and added an Alembic migration for the stored data. The signal tests pass (32 passed, 1 skipped); I didn't run the full suite, and I didn't run the migration against a database.

- **Backend:** `SignalFilterAction.merge = "merge"` replaces the old member. The references in `signal/service.py` and `signal/flows.py` are updated, including the comments that said "deduplicated".
- **Web UI:**
  - The create dialog radio now reads "Merge" with value `merge`.
  - The `v-if` check in that dialog uses `'merge'`.
  - The instance table's color and label maps are keyed on `merge`. I left the chip label text as "Duplicate", which you didn't ask me to change.
- **Migration:** `2025-09-02_a3c1e5d7b9f2.py` revises `ff08d822ef2c`, the previous head. It updates `signal_filter.action` and `signal_instance.filter_action` from `deduplicate` to `merge`, and the downgrade reverses that.
- **Tests:** `tests/factories.py` and `tests/signal/test_signal_service.py` use the new name, including test function names and comments.
- **Check:** a case-insensitive search of `src/dispatch` finds the word only inside the migration files.

I also changed `docs/scripts/openapi.yaml` to list `merge` as the enum value. I left the prose in `docs/docs/administration/settings/signal/filter.mdx`, which still says "deduplicate" and "Deduplication Filter", because it describes the behavior rather than the enum value.