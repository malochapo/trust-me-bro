`deduplicate` is now `merge` across the backend, web UI and stored data, and the signal tests pass (32 passed, 1 skipped). I didn't run the full test suite.

- **Backend:** `SignalFilterAction.merge = "merge"` replaces the old member in `signal/models.py`, with the usages updated in `signal/service.py` and `signal/flows.py`.
- **Migration:** `2025-09-02_a7c3e91d5b24.py` in the tenant revisions rewrites `signal_filter.action` and `signal_instance.filter_action` from `deduplicate` to `merge`. Its downgrade reverses that. I haven't run the migration against a database.
- **Web UI:** the filter dialog radio now sends `merge`, and the instance table maps `merge` for its chip color and label. I changed the visible labels too: "Deduplicate" is now "Merge" and "Duplicate" is now "Merged".
- **Tests and docs:** the existing tests and `tests/factories.py` use the new name, and `docs/scripts/openapi.yaml` has the new enum value.

A case-insensitive grep for `deduplicat` in `src/dispatch` (outside the migrations) still matches some prose:
- Comments and docstrings in `signal/service.py` say "deduplication".
- A comment in `static/dispatch/src/signal/instance/store.js` says "exclude deduplications".
- Help text in `static/dispatch/src/signal/NewEditDialog.vue` says "Snooze" or "Deduplication".

The exact word `deduplicate` no longer appears there, which is what you asked for. I left that prose as it was, and I can reword it if you want.

I didn't touch the "deduplicate" wording in `docs/docs/administration/settings/signal/filter.mdx`.