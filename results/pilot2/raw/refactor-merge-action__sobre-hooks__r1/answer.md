`deduplicate` is now `merge` everywhere, and the word no longer appears in `src/dispatch` outside the migration. I ran `python -m pytest tests/signal`: 32 passed, 1 skipped. I did not run the new migration against a database or open the web UI.

- **Backend:** `SignalFilterAction.merge = "merge"` in `signal/models.py`, plus its uses in `signal/service.py` and `signal/flows.py`.
- **Web UI:** the radio option (label "Merge", value `merge`) and its conditional in `SignalFilterCreateDialog.vue`, and the chip color and label keys in `TableInstanceTriggers.vue`.
- **Migration:** `2025-09-02_a3c1d5e7b9f2.py` sits after `ff08d822ef2c`. It rewrites `signal_filter.action` and `signal_instance.filter_action` from `deduplicate` to `merge`, and the downgrade reverses it.
- **Tests:** `tests/factories.py` and `tests/signal/test_signal_service.py` use the new name.

Related names like `filter_dedup`, `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` and the "deduplication" wording in some comments and help text are unchanged, since they aren't the word `deduplicate`.

I also changed the word `deduplicated` to `merged` in a few comments and test comments. In the UI, the instance table still shows the label "Duplicate" for merged instances, as before.