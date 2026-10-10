`deduplicate` is now `merge` throughout, and a new Alembic migration rewrites the rows already in the database. `python -m pytest tests/signal` gives 32 passed, 1 skipped. I didn't run the full suite, run the migration against a database, or check the web UI.

- **Backend:** the `SignalFilterAction` member is now `merge = "merge"`, and every use in `signal/service.py`, `signal/flows.py` and `signal/models.py` is updated. Comments that said "deduplicated" now say "merged".
- **Web UI:**
  - `SignalFilterCreateDialog.vue`: the radio's value is `merge` and its label reads "Merge".
  - `TableInstanceTriggers.vue`: the color and label map keys are `merge`. I left that label text as "Duplicate", which doesn't contain the word.
- **Migration:** `src/dispatch/database/revisions/tenant/versions/2025-09-02_8c1e5b7a4d20.py` follows the current head `ff08d822ef2c`. It updates `signal_filter.action` and `signal_instance.filter_action` from `deduplicate` to `merge`, and the downgrade reverses it. Both columns are plain strings, so only the values change.
- **Tests:** `tests/factories.py` and `tests/signal/test_signal_service.py` use the new name. That includes the test function names, such as `test_filter_actions_merge`.
- **Docs (beyond what you asked):** I also changed the enum in `docs/scripts/openapi.yaml` and two sentences in `docs/docs/administration/settings/signal/filter.mdx`.

A grep of `src/dispatch` finds the word only in the new migration.

I didn't commit anything.