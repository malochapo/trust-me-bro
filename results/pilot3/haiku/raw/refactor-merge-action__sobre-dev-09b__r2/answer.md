The `deduplicate` action is now `merge` throughout, and the signal tests pass (32 passed, 1 skipped). I did not run the Alembic migration against the database; I only confirmed it loads and chains onto the current head.

- **Enum:** `SignalFilterAction.deduplicate = "deduplicate"` is now `merge = "merge"` in `src/dispatch/signal/models.py`.
- **Backend:** the call sites in `service.py` and `flows.py` now use `SignalFilterAction.merge`. Comments that said "deduplicated" now say "merged".
- **Web UI:** the filter dialog radio is now `value="merge"` with the label "Merge". The instance table color and text maps use `merge`; the chip text still reads "Duplicate", which I left unchanged.
- **Tests:** `tests/factories.py` and `tests/signal/test_signal_service.py` use the new name, including test function names.
- **Migration:** `src/dispatch/database/revisions/tenant/versions/2026-10-11_5e1b7c9d3a24.py` revises `ff08d822ef2c`. Its upgrade rewrites `signal_filter.action` and `signal_instance.filter_action` from `deduplicate` to `merge`. Its downgrade reverses that.
- **Beyond `src/dispatch`:** I also updated the OpenAPI enum in `docs/scripts/openapi.yaml` and the filter docs page, since both describe the action value. Say if you'd rather keep those out of this change.

A grep for `deduplicate` now returns nothing outside the migrations, across the whole repo. I left "deduplication" concept names such as `filter_dedup` and "Deduplication Filter" alone, since they don't contain the word `deduplicate`.