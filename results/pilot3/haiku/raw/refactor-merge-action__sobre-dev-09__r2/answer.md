The `deduplicate` action is now `merge` throughout, with an Alembic data migration for existing rows. The signal tests pass (32 passed, 1 skipped). The full suite has 8 failures, and the same 8 fail on the untouched tree.

**What changed**
- **Enum:** `SignalFilterAction.deduplicate = "deduplicate"` is now `merge = "merge"` in `src/dispatch/signal/models.py`.
- **Backend:** all uses in `signal/service.py` and `signal/flows.py` now use `merge`. Two comments that said "deduplicated" now say "merged".
- **Web UI:** the filter create dialog radio is now "Merge" with value `merge`. The instance table colour and label maps key on `merge`. The `store.js` filter comment now says "exclude merges". The tooltip in `NewEditDialog.vue` now says "Merge".
- **Tests and factories:** `tests/factories.py` and `tests/signal/test_signal_service.py` use `merge`. Test function names that contained `deduplicate` were renamed to match.
- **Migration:** `src/dispatch/database/revisions/tenant/versions/2026-10-10_988482f2c596.py`, revising `ff08d822ef2c`, the current tenant head. Upgrade rewrites `signal_filter.action` and `signal_instance.filter_action` from `'deduplicate'` to `'merge'`. Downgrade reverses it. It compiles, but I did not run it against Postgres.
- **Docs:** `docs/scripts/openapi.yaml` enum value and one sentence in `docs/docs/administration/settings/signal/filter.mdx`.

`grep -ri deduplicate src/dispatch` now returns nothing outside the migrations.

**Choices I made**
- The "Duplicate" chip label in the instance table is unchanged. It describes the instance rather than the action name, so I left it alone.
- The conceptual word "deduplication" remains in some comments and in the default one-hour dedup prose in `filter.mdx`. It does not contain the string `deduplicate`, and it describes the feature rather than the action.

**Test failures**
The 8 failures are `tests/ai/test_ai_service.py` (6), `tests/database/test_service.py::test_restricted_case_filter_with_test_data`, and `tests/entity/test_entity_service.py::test_find_entities_with_field_only`. They fail identically on the clean tree, so they are not caused by this change.