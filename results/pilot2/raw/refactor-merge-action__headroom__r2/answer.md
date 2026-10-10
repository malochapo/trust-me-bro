I renamed `deduplicate` to `merge` throughout the backend, the web UI and the tests. I also added a migration that rewrites the existing rows. The signal tests pass (32 passed, 1 skipped). I did not run the full suite, and I did not run the migration against a database.

- **Backend:** `SignalFilterAction.merge = "merge"` replaces the old member, and `signal/service.py` and `signal/flows.py` use the new name. I also reworded the two comments that said "deduplicated" or "deduplicate".
- **Web UI:** the filter create dialog now has a "Merge" radio option with value `merge`. In `TableInstanceTriggers.vue` the color and label maps are keyed by `merge`. I left the displayed label as "Duplicate", since you asked for no behavior change.
- **Tests:** `tests/factories.py` and `tests/signal/test_signal_service.py` use the new name, including the test function names.
- **Migration:** `2025-09-02_a1c3e5f7b9d2.py` follows `ff08d822ef2c`. It updates `signal_filter.action` and `signal_instance.filter_action` from `deduplicate` to `merge`, and the downgrade reverses that.

A case-insensitive grep for `deduplicate` in `src` and `tests`, excluding the migrations folder, now returns nothing.