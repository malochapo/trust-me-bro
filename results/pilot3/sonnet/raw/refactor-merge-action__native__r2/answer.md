`deduplicate` is now `merge` throughout, and a new migration rewrites the stored values. `tests/signal` passes (32 passed, 1 skipped); I didn't run the rest of the suite or run the migration itself.

- **Backend:** `SignalFilterAction.merge = "merge"` replaces the old member, and `service.py` and `flows.py` use it. Behavior is unchanged.
- **Web UI:** the radio value and its `v-if` check in `SignalFilterCreateDialog.vue` now use `merge`. The radio label reads "Merge" instead of "Deduplicate". In `TableInstanceTriggers.vue` the color and label keys are renamed.
- **UI label left as is:** the instance table still displays the text "Duplicate" for that action. I didn't change it, since you asked for no behavior change.
- **Tests:** `tests/factories.py` and `tests/signal/test_signal_service.py` use the new name. That includes test function names, comments and the `action="merge"` arguments.
- **Wording:** I also changed "deduplicated" in comments to "merged", because the word couldn't remain in `src/dispatch` and "deduplicated" contains it.
- **Migration:** `src/dispatch/database/revisions/tenant/versions/2025-09-02_a3c7e1d4b9f2.py` follows `ff08d822ef2c`. It sets `signal_filter.action` and `signal_instance.filter_action` from `'deduplicate'` to `'merge'`, and the downgrade reverses that.

A final grep finds no `deduplicate` left in `src/dispatch` outside the migrations.