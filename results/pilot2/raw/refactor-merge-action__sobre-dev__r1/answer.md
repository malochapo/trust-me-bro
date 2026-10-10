Table names default to `signal_filter` and `signal_instance` (Dispatch's snake-case convention), matching the migration.

`deduplicate` is now `merge` everywhere in `src/dispatch` outside the migrations. I ran `tests/signal`, which had 32 pass and 1 skipped. I did not run the migration against a database or run the rest of the suite.

- **Backend:** the `SignalFilterAction.merge` member (value `"merge"`) replaces the old one in `signal/models.py`, `signal/service.py` and `signal/flows.py`. I also changed the comment in `flows.py` from "deduplicated" to "merged".
- **Web UI:** the radio option in `SignalFilterCreateDialog.vue` is now "Merge", with its value and the `v-if` check renamed. `TableInstanceTriggers.vue` has the `merge` key for the color and label maps. I left its displayed label as "Duplicate", since you asked for no behavior change.
- **Migration:** `2025-09-02_3c1b7d9e5a42.py` follows `ff08d822ef2c`. It updates `signal_filter.action` and `signal_instance.filter_action` from `deduplicate` to `merge`, and the downgrade reverses it. Both columns are plain strings, so no database enum needs altering.
- **Tests:** `tests/factories.py` and `tests/signal/test_signal_service.py` use the new name, including test function names, comments and docstrings.

The old word still appears in the new migration, which is allowed.