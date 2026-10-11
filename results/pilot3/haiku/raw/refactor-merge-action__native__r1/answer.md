The signal filter action is renamed from `deduplicate` to `merge` across the backend, the web UI, and the tests, with a tenant migration that rewrites stored values. The signal test suite passes (32 passed, 1 skipped). `deduplicate` no longer appears anywhere in `src/dispatch` outside the migrations.

**What changed**
- **Enum:** `SignalFilterAction.deduplicate = "deduplicate"` is now `merge = "merge"` in `src/dispatch/signal/models.py`.
- **Usages:** `service.py` and `flows.py` use `SignalFilterAction.merge`. The comment in `flows.py` now says "merged".
- **Web UI:**
  - `SignalFilterCreateDialog.vue`: the radio is now value `merge`, labelled "Merge" (the label changed from "Deduplicate").
  - `TableInstanceTriggers.vue`: the color and label map key is `merge`. The displayed text stays "Duplicate", so the instance table looks the same.
- **Migration:** `src/dispatch/database/revisions/tenant/versions/2026-10-10_6ee3f082fc2f.py`, revising the current head `ff08d822ef2c`. It updates `signal_filter.action` and `signal_instance.filter_action` from `deduplicate` to `merge`. I also wrote a downgrade that reverses it.
- **Tests:** `tests/factories.py` and `tests/signal/test_signal_service.py` use `merge`. I also renamed the test functions that had `deduplicate` in their names.

**Choices you may want to revisit**
- The "Merge" radio label is a visible wording change, not just a value change. Say if you want "Deduplicate" kept as the label.
- Comments and test names still say "deduplication" or "deduplicated" in places. I left them, since that's a different word and the constraint was about `deduplicate`.

**Things to know**
- **Test database port:** the environment sets `DATABASE_PORT=5434`, but that server's template database is `SQL_ASCII`, so the test harness can't create its UTF8 database and every test errors at setup. The UTF8 server on 5432 works. I ran the tests with `DATABASE_PORT=5432 python -m pytest ...` for that command only and didn't change the environment.
- **Migration verification:** I confirmed the chain has a single head, `6ee3f082fc2f`, but I did not run the migration against a database. The SQL is two plain `UPDATE`s, and both columns are plain strings, not Postgres enums, so no type change is needed.
- **Formatting:** black flags `models.py` and two other test files, but those warnings were already there before my change. I formatted only the new migration.
- **Outside `src/dispatch`:** the docs still describe the action as "Deduplication". `docs/scripts/openapi.yaml` (around line 4514) still lists `deduplicate` as an enum value, so it is now stale until it is regenerated or hand-edited. I didn't touch either, since they are outside the requested scope.