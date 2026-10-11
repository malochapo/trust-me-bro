I renamed `deduplicate` to `merge` throughout. The `tests/signal` run gives 32 passed and 1 skipped; I didn't run the rest of the suite.

- **Backend:** `SignalFilterAction.merge = "merge"` in `signal/models.py`, plus the uses in `signal/service.py` and `signal/flows.py`. I also changed the comments that said "deduplicated" to "merged".
- **Web UI:** `SignalFilterCreateDialog.vue` now has a "Merge" radio with value `merge`. `TableInstanceTriggers.vue` uses the `merge` key for the chip colour and label.
- **Tests:** `tests/factories.py` and `tests/signal/test_signal_service.py` use the new name, including the test function names.
- **Migration:** `tenant/versions/2025-09-02_a3c1d5e7b9f2.py` follows `ff08d822ef2c`. It updates `signal_filter.action` and `signal_instance.filter_action` from `deduplicate` to `merge`. The downgrade reverses it. I haven't run the migration against a database.
- **Check:** a case-insensitive grep finds no `deduplicate` in `src/dispatch` outside the migrations.

I left the instance-table chip text as "Duplicate", since you asked for no behaviour change. Say if you want it to read "Merged".