The rename is done. `deduplicate` no longer appears anywhere in `src/dispatch` outside the revisions directory, and the signal tests pass.

**What changed**
- **Enum:** `SignalFilterAction.deduplicate = "deduplicate"` is now `merge = "merge"` in `src/dispatch/signal/models.py`.
- **Backend:** `signal/service.py` and `signal/flows.py` use `SignalFilterAction.merge`. I also reworded the comments that said "deduplicated" to "merged". Function names like `filter_dedup` and the "Deduplication" wording are unchanged, since they don't contain the word `deduplicate`.
- **Web UI:** the filter create dialog's radio is now labelled "Merge" with value `merge`. In `TableInstanceTriggers.vue` the key is `merge`; the displayed text is still "Duplicate", so the UI wording stays the same.
- **Tests:** `tests/factories.py` and `tests/signal/test_signal_service.py` use the new name, including test function names.
- **Data migration:** `src/dispatch/database/revisions/tenant/versions/2026-10-11_005d04d52496.py`, revising the current tenant head `ff08d822ef2c`. Its upgrade rewrites `signal_filter.action` and `signal_instance.filter_action` from `'deduplicate'` to `'merge'`. Downgrade reverses it. Both columns are plain strings, so no PostgreSQL enum type needs changing.
- **Docs (outside `src/dispatch`):** I also updated the enum entry in `docs/scripts/openapi.yaml` and two sentences in `filter.mdx`, so the docs match the API. Say if you'd rather I leave `docs/` alone.

**Verification**
- `python -m pytest tests/signal`: 32 passed, 1 skipped.
- Full `python -m pytest tests`: 359 passed, 4 skipped, 8 failed. The 8 failures are in `tests/ai/test_ai_service.py`, `tests/database/test_service.py::test_restricted_case_filter_with_test_data` and `tests/entity/test_entity_service.py::test_find_entities_with_field_only`. I stashed my changes and got the same 8 failures on the untouched tree, so they predate this work.
- The migration has a single Alembic head. I did not run it against a PostgreSQL database, so the upgrade and downgrade SQL is unexecuted.