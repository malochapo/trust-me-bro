The rename is done across the backend, web UI, and tests, and there's a new migration rewriting stored values. `tests/signal` passes (32 passed, 1 skipped). I did not run the full suite or execute the migration against a database.

- **Enum:** `SignalFilterAction.deduplicate = "deduplicate"` is now `merge = "merge"` in `src/dispatch/signal/models.py`.
- **Backend:** `service.py` and `flows.py` use `SignalFilterAction.merge`. Comments that said "deduplicated" now say "merged".
- **Web UI:** `SignalFilterCreateDialog.vue` has a "Merge" radio with value `merge`. `TableInstanceTriggers.vue` maps `merge` to the same "Duplicate" chip label as before, so the displayed text is unchanged.
- **Tests:** `tests/factories.py` and `tests/signal/test_signal_service.py` use the new name. I also renamed the test functions that contained `deduplicate`.
- **Migration:** `src/dispatch/database/revisions/tenant/versions/2026-10-11_2f53261adeba.py` revises the current head `ff08d822ef2c`. Upgrade rewrites `signal_filter.action` and `signal_instance.filter_action` from `deduplicate` to `merge`. Downgrade reverses it. Both columns are plain strings, so no enum type change is needed.
- **OpenAPI:** I also changed the enum value in `docs/scripts/openapi.yaml`, since it documents the API value.

`grep -i deduplicate` over `src/dispatch` and `tests` now returns nothing outside the migrations. The word "deduplication" still appears in a few places (service docstrings and a UI label). That's the concept noun, not the `deduplicate` identifier, so I left it.

Two things I did not touch:
- `docs/docs/administration/settings/signal/filter.mdx` still uses "deduplicate" in its prose. It's outside `src/dispatch`, so I left it. Say if you want it updated.
- `ruff format --check` flags three files in `src/dispatch/signal` and `tests/signal` both before and after my change. The new migration passes lint and format.