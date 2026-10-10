The signal filter action `deduplicate` is now `merge` throughout, and the signal tests pass (32 passed, 1 skipped). I only ran `tests/signal`, not the full suite.

- **Code:** `SignalFilterAction.merge = "merge"` replaces the old member in `signal/models.py`. `service.py` and `flows.py` use the new name, and the behavior is unchanged.
- **Web UI:** `TableInstanceTriggers.vue` and `SignalFilterCreateDialog.vue` use the new key, and the radio label now reads "Merge".
- **Migration:** `tenant/versions/2025-09-02_a7c3e91d5b24.py` follows the previous head `ff08d822ef2c`. It rewrites `signal_filter.action` and `signal_instance.filter_action` from `deduplicate` to `merge`, and the downgrade reverses it. I didn't run the migration against a database.
- **Tests:** `tests/factories.py` and `tests/signal/test_signal_service.py` use the new name. I also renamed test functions and comments that contained the old word.
- **Docs:** I updated `docs/scripts/openapi.yaml` and `filter.mdx` as well, which you didn't ask for.

The word `deduplicate` no longer appears anywhere in `src/dispatch` outside the migrations. A few related words remain there: "deduplication" in some comments in `signal/service.py`, plus the "Deduplication" wording in `NewEditDialog.vue` and the `store.js` comment. I left those, and the "Duplicate" chip label in `TableInstanceTriggers.vue`, since they don't contain the old word.