I renamed `deduplicate` to `merge` throughout, and the signal tests pass (32 passed, 1 skipped). I didn't run the new migration against a database, and I didn't run the rest of the suite.

- **Backend:** `SignalFilterAction.merge = "merge"` replaces the old member. The references in `signal/service.py` and `signal/flows.py` now use it, and comments and docstrings that said "deduplicated" now say "merged".
- **Web UI:** `TableInstanceTriggers.vue` and `SignalFilterCreateDialog.vue` use `merge`. The radio label now reads "Merge", and the chip label for merged instances is still "Duplicate".
- **Tests, factories and docs:** I updated `tests/signal/test_signal_service.py` and `tests/factories.py`. I also changed the enum value in `docs/scripts/openapi.yaml`, which you didn't list.
- **Migration:** `2025-09-02_a7c3e91d5b24.py` follows `ff08d822ef2c`. It rewrites `signal_filter.action` and `signal_instance.filter_action` from `deduplicate` to `merge`, and the downgrade reverses that.

A case-insensitive search of `src/dispatch` finds no `deduplicate` outside the revisions directory.

Related names such as `filter_dedup`, `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` and the word "Deduplication" are unchanged, because they don't contain the word `deduplicate`. That leaves the "Deduplication" wording in `signal/NewEditDialog.vue` and the docs `filter.mdx` text unchanged. Say if you want those renamed too.