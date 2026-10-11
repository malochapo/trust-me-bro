The rename is done. `deduplicate` no longer appears anywhere under `src/dispatch` or `tests`, except in the migrations directory.

**What changed**
- **Enum:** `SignalFilterAction.deduplicate = "deduplicate"` is now `merge = "merge"` in `src/dispatch/signal/models.py`.
- **Backend:** `service.py` and `flows.py` use `SignalFilterAction.merge`. Comments that said "deduplicated" now say "merged".
- **Web UI:** `SignalFilterCreateDialog.vue` and `TableInstanceTriggers.vue` use the `merge` value.
- **Tests:** `tests/factories.py` and `tests/signal/test_signal_service.py` are updated, including test names such as `test_filter_actions_merge_different_entities`.
- **Migration:** `src/dispatch/database/revisions/tenant/versions/2026-10-11_5e1a9c3d7b42.py` (revision `5e1a9c3d7b42`, revises the current head `ff08d822ef2c`). Upgrade rewrites `signal_filter.action` and `signal_instance.filter_action` from `'deduplicate'` to `'merge'`. Downgrade reverses it.
- **API spec:** the `SignalFilterAction` enum in `docs/scripts/openapi.yaml` now lists `merge`.

**Choices to review**
- The dialog radio label changed from "Deduplicate" to "Merge" so it matches the value. This is a visible UI text change.
- The chip text "Duplicate" in `TableInstanceTriggers.vue` is unchanged, since it doesn't contain the old word.
- I left the docs under `docs/docs/` alone because they are outside `src/dispatch`. `filter.mdx` still describes a "Deduplication" radio button, which no longer matches the UI label. Say if you want those updated too.

**Verification**
- `python -m pytest tests/signal`: 32 passed, 1 skipped.
- Full `python -m pytest`: 359 passed, 4 skipped, 8 failed.
  - Six failures in `tests/ai/test_ai_service.py` need to download a tokenizer file, which fails without network access.
  - `test_restricted_case_filter_with_test_data` and `test_find_entities_with_field_only` also fail on the untouched code, so they predate this change.
- I checked that the migration compiles. I did not run it against a database, and I did not run a formatter because `ruff` isn't installed here.