I renamed `deduplicate` to `merge` throughout, and `deduplicate` no longer appears anywhere in `src/dispatch` outside the migrations. `python -m pytest tests/signal` gives 32 passed, 1 skipped. I didn't run the new migration or the web UI, so neither has been exercised.

- **Backend:** `SignalFilterAction.merge = "merge"` replaces the old member in `signal/models.py`. `service.py` and `flows.py` use it, and the comments that said "deduplicated" now say "merged".
- **Web UI:** the radio value and condition in `SignalFilterCreateDialog.vue` and the color and label keys in `TableInstanceTriggers.vue` use `merge`. The radio's visible label changed from "Deduplicate" to "Merge".
- **Migration:** `2025-09-02_a3c1d9e47b52.py` follows `ff08d822ef2c`. It rewrites `signal_filter.action` and `signal_instance.filter_action` from `deduplicate` to `merge`, and its downgrade reverses that.
- **Tests:** `tests/factories.py` and `tests/signal/test_signal_service.py` use the new name, including test function names.
- **Docs:** I also updated `docs/scripts/openapi.yaml` and one sentence in `docs/docs/administration/settings/signal/filter.mdx`. `filter.mdx` still says "Deduplication Filter" and "deduplicated" in another sentence.

I left the "Duplicate" badge text in `TableInstanceTriggers.vue` as it was, since it's display text only. Say if you want it to read "Merge" too.