`deduplicate` is now `merge` in the backend, the web UI and the stored data, and `tests/signal` passes (32 passed, 1 skipped). I haven't run the full suite or the migration itself.

- **Backend:** the enum member and value in `signal/models.py`, plus the uses in `signal/service.py` and `signal/flows.py`.
- **Web UI:** the radio option and its value in `SignalFilterCreateDialog.vue`, and the color and label map keys in `TableInstanceTriggers.vue`.
- **Tests:** the factory choices and the existing tests in `tests/signal/test_signal_service.py`.
- **Migration:** `2025-09-02_a7c3e91d5b24.py` follows `ff08d822ef2c`. It updates `signal_filter.action` and `signal_instance.filter_action` from `deduplicate` to `merge`, and the downgrade reverses that.

The word `deduplicate` no longer appears in `src/dispatch` outside the migrations. Related words like "deduplication", `filter_dedup` and `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` are still there, since they weren't part of the rename. The UI label for merged instances still says "Duplicate"; I left it as it was.