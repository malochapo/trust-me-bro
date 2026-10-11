The signal filter action `deduplicate` is now `merge` everywhere, including the stored values. The word no longer appears in `src/dispatch` outside the migrations. The signal tests pass (32 passed, 1 skipped), and the migration round-trips correctly against Postgres.

**What changed**
- **Enum:** `SignalFilterAction.deduplicate = "deduplicate"` is now `merge = "merge"` (`src/dispatch/signal/models.py`). The `filter_action` and `action` columns are plain strings, so no Postgres enum type needed changing.
- **Backend:** `service.py` and `flows.py` use the new member, and the `flows.py` comment says "merged" instead of "deduplicated".
- **Web UI:** The filter create dialog's radio is now labelled "Merge" with value `merge`, and the tooltip in `NewEditDialog.vue` says "Merge". `TableInstanceTriggers.vue` keys on `merge` but still displays "Duplicate" for instances, so the instance label is unchanged.
- **Tests:** `tests/signal/test_signal_service.py` and `tests/factories.py` use the new name. I also renamed test function names that contained `deduplicate`.
- **Migration:** `src/dispatch/database/revisions/tenant/versions/2026-10-10_a86d71e95ad2.py`, revising the current head `ff08d822ef2c`. Upgrade rewrites `signal_filter.action` and `signal_instance.filter_action` from `deduplicate` to `merge`. Downgrade reverses it.
- **Docs:** `docs/scripts/openapi.yaml` enum value and the radio name in `filter.mdx`.

**Verification**
- Migration: I ran `upgrade()` and `downgrade()` against a scratch schema. Rows with `deduplicate` became `merge` and back. `snooze`, `none`, and NULL were untouched. I did not run `alembic upgrade` on a real tenant database.
- Full suite: 8 tests fail in `tests/ai/test_ai_service.py`, `tests/database/test_service.py`, and `tests/entity/test_entity_service.py`. They fail the same way on the untouched tree, so they predate this change.
- `black` and `ruff` aren't installed here, so I only checked the migration's line lengths against the 100-character limit.

**Choices to check**
- I kept the feature name "Deduplication Filter" in the docs and the phrase "deduplication" in comments and docstrings. The constraint only covered the word `deduplicate`.
- The UI labels "Deduplicate" and "Deduplication" are now "Merge", which is a visible text change in the filter dialog. I treated that as part of renaming the action, but it is the one place where behaviour text moved.