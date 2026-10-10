`deduplicate` is now `merge` everywhere in `src/dispatch` outside the migrations, and the signal tests pass (32 passed, 1 skipped).

- **Backend:** `SignalFilterAction.merge = "merge"` replaces `deduplicate` in `signal/models.py`, and `signal/service.py` and `signal/flows.py` use the new member.
- **Web UI:** `TableInstanceTriggers.vue` and `SignalFilterCreateDialog.vue` use the `merge` value. The radio button now reads "Merge", but the chip for merged instances still says "Duplicate". `NewEditDialog.vue` help text and a comment in `store.js` were reworded too.
- **Migration:** `2025-09-02_3b1c7e9a5d42.py` follows `ff08d822ef2c`, the current head. It updates `signal_filter.action` and `signal_instance.filter_action` from `deduplicate` to `merge`, and reverses that on downgrade. I did not run the migration against a database, only the test suite.
- **Tests:** `tests/factories.py` and `tests/signal/test_signal_service.py` use the new name.

I also changed comments and docstrings that said "deduplicated" or "deduplication", so the word is gone entirely rather than just the enum.

Outside `src/dispatch`, I also updated `docs/scripts/openapi.yaml` and `docs/docs/administration/settings/signal/filter.mdx`, which you didn't ask for. I ran the signal tests (`tests/signal`) only, not the full suite.