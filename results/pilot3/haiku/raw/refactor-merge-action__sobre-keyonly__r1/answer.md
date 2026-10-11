The `deduplicate` action is now `merge` throughout, with an Alembic migration that rewrites stored values. No `deduplicate` remains in `src/dispatch` outside the migrations. The signal tests pass (32 passed, 1 skipped). The full suite has 8 failures, and the same 8 fail on the untouched baseline (AI service and a few database/entity tests), so they predate this change.

**What changed**
- **Enum:** `SignalFilterAction.deduplicate = "deduplicate"` is now `merge = "merge"` in `src/dispatch/signal/models.py`.
- **Backend:** the uses in `signal/service.py` and `signal/flows.py` now reference `merge`, and the comments that said "deduplicated" now say "merged".
- **Web UI:** the filter dialog radio is now `value="merge"` with the label "Merge". The instance chip key is `merge`, but its display text stays "Duplicate" so the visible behavior of existing rows is unchanged.
- **Migration:** `src/dispatch/database/revisions/tenant/versions/2026-10-11_3c9d1f7a8e25.py`, revising the current head `ff08d822ef2c`. Upgrade updates `signal_filter.action` and `signal_instance.filter_action` from `deduplicate` to `merge`. Downgrade reverses it. Both columns are plain strings, so no PostgreSQL enum type needed changing.
- **Tests:** `tests/factories.py` and `tests/signal/test_signal_service.py` use `merge`, including test names and comments.
- **Docs:** `docs/scripts/openapi.yaml` and `docs/docs/administration/settings/signal/filter.mdx` also use `merge`, since they're part of "everywhere".

**Choices and limits**
- I left "Deduplication" / "dedup" identifiers alone (`filter_dedup`, `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`, "Deduplication Filter" in the docs). They don't contain the word `deduplicate`, and renaming them wasn't asked for.
- I compiled the migration but did not run `alembic upgrade` against a database, so the UPDATE statements are unexecuted. The table names come from the model's auto-naming and the original `signal_filter` creation migration.