The rename is done and the signal tests pass (32 passed, 1 skipped), but I did not run the migration against a database.

**What changed**
- **Enum:** `SignalFilterAction.deduplicate = "deduplicate"` is now `merge = "merge"` in `src/dispatch/signal/models.py`.
- **Backend:** `flows.py` and `service.py` use `SignalFilterAction.merge`. Comments that said "deduplicated" now say "merged".
- **Web UI:** the filter dialog's radio button is now "Merge" with value `merge`, and the instance table's chip color/key uses `merge`.
- **Tests:** `tests/factories.py` and `tests/signal/test_signal_service.py` use the new name, including the test function names.
- **Migration:** `src/dispatch/database/revisions/tenant/versions/2026-10-10_3c9f1e7a5b20.py` sets `revision` to `3c9f1e7a5b20` and `down_revision` to `ff08d822ef2c`, the previous head. Its `upgrade()` rewrites `'deduplicate'` to `'merge'` in `signal_filter.action` and `signal_instance.filter_action`. `downgrade()` reverses it. Both columns are plain `String`, so no Postgres enum type needed changing.

**Beyond `src/dispatch`**
- I also updated `docs/scripts/openapi.yaml` (the enum value) and `docs/docs/administration/settings/signal/filter.mdx`, since "everywhere" covered them.
- The chip text "Duplicate" in the instance table is unchanged, because it's a display label rather than the action name.
- The docs still say "Deduplication Filter" as a concept name, which I left alone.

**Verification**
- `grep -i deduplicate` over `src/dispatch`, `tests`, and `docs` returns nothing outside the new migration. The existing migrations never contained the word.
- `python -m pytest tests/signal` passes.
- The migration file compiles. I could not check Alembic's head with `ScriptDirectory` because the app config needs `DISPATCH_ENCRYPTION_KEY` set, which this environment doesn't have. Based on reading the revision chain, `ff08d822ef2c` was the only head and the new file extends it.
- I have not run `alembic upgrade` / `downgrade` against a database, so the UPDATE statements are unexecuted. Running them on a populated tenant schema would be the next check.

Nothing is committed.