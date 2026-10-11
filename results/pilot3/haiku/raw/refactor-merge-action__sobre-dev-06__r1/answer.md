The rename is done across the backend, web UI, tests, and docs, and the tenant migration is in place. The signal tests pass (32 passed, 1 skipped). The full suite has 8 failures, all in `tests/ai`, `tests/database` and `tests/entity`, and they fail the same way on the untouched tree.

**What changed**
- **Enum:** `SignalFilterAction.deduplicate = "deduplicate"` is now `merge = "merge"` in `src/dispatch/signal/models.py`. `service.py`, `flows.py`, and the `tests/factories.py` fixture use the new member.
- **Web UI:** the filter dialog radio is now labelled "Merge" with value `merge`. The instance table chip maps `merge` to the same colour as before. Its display text stays "Duplicate" so the UI reads the same as it did.
- **Migration:** `src/dispatch/database/revisions/tenant/versions/2026-10-10_823908631415.py` chains onto the current head `ff08d822ef2c`. Its upgrade rewrites `signal_filter.action` and `signal_instance.filter_action` from `deduplicate` to `merge`. The downgrade reverses it. Both columns are plain strings, so no Postgres enum type needed changing.
- **Tests:** `tests/signal/test_signal_service.py` uses the new name and renamed test functions, and comments say "merged".
- **Docs:** I also updated `docs/scripts/openapi.yaml` and one sentence each in `filter.mdx`. You asked for "everywhere", so I took that to include these.

**Verification**
- `grep -ri deduplicate src/dispatch` finds matches only in the migrations folder, where the new migration's downgrade names the old value.
- The migration chain has a single head, `823908631415`.

**Not verified**
- I did not run the migration against a live database, so the `UPDATE` statements are checked by reading, not by execution.