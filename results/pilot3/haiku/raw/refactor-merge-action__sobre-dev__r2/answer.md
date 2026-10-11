The signal filter action is now `merge` everywhere in `src/dispatch`, with a tenant Alembic migration that rewrites the stored values. The signal tests pass (32 passed, 1 skipped). The full suite has 8 failures, and the same 8 fail on the untouched baseline, so they are not from this change.

**What changed**
- **Enum:** `SignalFilterAction.deduplicate = "deduplicate"` is now `merge = "merge"` in `signal/models.py`. Usages in `signal/service.py` and `signal/flows.py` follow it.
- **Web UI:** the filter dialog radio is now value `merge` with label "Merge" (was "Deduplicate"). The instance triggers map key is `merge`; I kept its existing "Duplicate" display text. The help tooltip in `NewEditDialog.vue` now says "Merge".
- **Tests:** `tests/signal/test_signal_service.py` and `tests/factories.py` use `merge`. I also renamed the test functions and comments that contained the word.
- **API spec:** `docs/scripts/openapi.yaml` enum value updated to `merge`, since it describes the stored/API value.
- **Migration:** `src/dispatch/database/revisions/tenant/versions/2026-10-10_73ea3bb9a950.py`, revising the current tenant head `ff08d822ef2c`. Upgrade rewrites `signal_filter.action` and `signal_instance.filter_action` from `deduplicate` to `merge`. Downgrade reverses it.

**Verification**
- `grep -i deduplicate` over `src/dispatch` (excluding migrations) returns nothing.
- The migration module loads and its parent is the single tenant head.
- I did not run the migration against a live database.

**Left alone (outside `src/dispatch`, or not the word)**
- `docs/docs/administration/settings/signal/filter.mdx` still says "deduplicate" in prose. It's user documentation, so it should be updated as a follow-up.
- Identifiers like `filter_dedup` and `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` are different words and unchanged.