I renamed `deduplicate` to `merge` throughout. The signal tests pass (32 passed, 1 skipped). I didn't run the new migration or the rest of the suite.

- **Backend:** `SignalFilterAction.deduplicate` is now `SignalFilterAction.merge`, with the value `"merge"`. The usages in `signal/service.py` and `signal/flows.py` are updated.
- **Web UI:** The radio option and the conditional in `SignalFilterCreateDialog.vue` and the colour and label maps in `TableInstanceTriggers.vue` now use `merge`. The visible labels now say "Merge", including the radio label, the dialog help text and a comment in `store.js`.
- **Migration:** `2025-09-02_a3c1d7e5b9f2.py` revises `ff08d822ef2c`. It rewrites `signal_filter.action` and `signal_instance.filter_action` from `deduplicate` to `merge`, and the downgrade reverses that. The table names come from the model classes, but I didn't confirm them against the existing revisions.
- **Tests and docs:** I updated `tests/factories.py` and `tests/signal/test_signal_service.py`. I also changed the docs: `docs/scripts/openapi.yaml` (the enum value) and the signal filter page (wording only).

A case-insensitive search of `src/dispatch` finds the old word only inside the new migration, which has to name it.

I also reworded related words such as "deduplicated" and "deduplication" in comments and UI text. The "Duplicate" label in `TableInstanceTriggers.vue` is unchanged, since it isn't the old word.