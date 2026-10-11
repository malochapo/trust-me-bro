The rename is done. `deduplicate` no longer appears anywhere in `src/dispatch` outside the migrations, and the signal tests pass (32 passed, 1 skipped).

**What changed**
- **Enum:** `SignalFilterAction.deduplicate = "deduplicate"` is now `merge = "merge"` in `src/dispatch/signal/models.py`.
- **Backend:** `service.py` and `flows.py` use `SignalFilterAction.merge`, and the comment in `flows.py` now says "merged".
- **Web UI:**
  - `SignalFilterCreateDialog.vue`: the radio is now `label="Merge" value="merge"`, and the `v-if` checks `'merge'`. The label changed from "Deduplicate" to "Merge".
  - `TableInstanceTriggers.vue`: the color and label map keys are `merge`. The chip text stays "Duplicate", so what users see there is unchanged.
- **Tests:** `tests/factories.py` and `tests/signal/test_signal_service.py` use the new value. I also renamed the test functions that had `deduplicate` in their names and their comments.
- **API spec:** `docs/scripts/openapi.yaml` lists `merge` in the `SignalFilterAction` enum, matching the code.
- **Migration:** new file `src/dispatch/database/revisions/tenant/versions/2025-10-11_c36235ef6ed4.py`, revising the current head `ff08d822ef2c`. The upgrade rewrites `signal_filter.action` and `signal_instance.filter_action` from `'deduplicate'` to `'merge'`. The downgrade reverses it. Both columns are plain strings, so no PostgreSQL enum type needs altering.

**Verification**
- I did not run the migration against a live PostgreSQL database.
- The full suite gives 359 passed, 4 skipped, 8 failed. The same 8 fail on a clean checkout of HEAD (`tests/ai/test_ai_service.py`, `tests/database/test_service.py::test_restricted_case_filter_with_test_data`, `tests/entity/test_entity_service.py::test_find_entities_with_field_only`), so they predate this change.

**Choices you may want to review**
- I changed the dialog label to "Merge" because the old label was the word itself. The chip text "Duplicate" was left alone.
- I left `docs/docs/administration/settings/signal/filter.mdx` alone. It describes the feature in prose ("Deduplication Filter") and is outside `src/dispatch`. Its one mention of the radio's value is "Deduplication", which I did not rename. Say if you want the docs updated too.