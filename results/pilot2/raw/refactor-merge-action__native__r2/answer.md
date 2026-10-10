`deduplicate` is now `merge` everywhere in `src/dispatch` outside the migrations, and a new migration rewrites the stored values. I ran `tests/signal` (32 passed, 1 skipped) but not the full suite. I did not run the migration against a database.

- **Backend:** `SignalFilterAction.merge = "merge"` replaces the old member in `signal/models.py`, and `signal/service.py` and `signal/flows.py` use it.
- **Web UI:** the radio value and conditional in `SignalFilterCreateDialog.vue` and the badge-colour map key in `TableInstanceTriggers.vue` now use `merge`. The radio label now reads "Merge" instead of "Deduplicate".
- **Migration:** `2025-09-02_3b7c1d9e5a42.py` follows head `ff08d822ef2c`. It updates `signal_filter.action` and `signal_instance.filter_action` from `deduplicate` to `merge`, and the downgrade reverses it. I assumed the table names `signal_filter` and `signal_instance` from the model class names and from existing migrations that reference `signal_instance`.
- **Tests:** `tests/factories.py` and `tests/signal/test_signal_service.py` use the new name, including the test function names.

I also renamed it in `docs/scripts/openapi.yaml` and `docs/docs/administration/settings/signal/filter.mdx`, which you didn't ask for.

The related word "deduplication" (a different string) still appears in some comments, `NewEditDialog.vue` help text and `store.js`, and the docs headings. I left those alone since they aren't the action name.