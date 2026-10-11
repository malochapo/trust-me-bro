Muting is implemented across the model, filter pipeline, API, migration, and UI. The signal tests pass. The full suite has 8 failures that also fail on a clean HEAD checkout, so they predate this change. I did not commit.

**How it works**

- **Model:** `Signal.muted_until` is a timezone-aware `DateTime`, nullable. `SignalBase` carries it, so create, update, and read accept and return it. An explicit `null` clears the mute.
- **Filtering:** `filter_mute` runs first in `filter_signal`. If `muted_until` is in the future, the instance gets `filter_action = mute`. Snooze and dedup only run when nothing was muted. The create flow already returns early on any filter action, so a muted instance is stored and never opens a case. Once the time passes, the check fails and normal processing resumes.
- **Migration:** `d5064d2935b6` adds the column to `signal`, with `ff08d822ef2c` (the current tenant head) as its parent.
- **Audit:** changes to `muted_until` are logged as signal events. The generic change logger skips datetime fields, so I added an explicit entry.
- **UI:** a "Muted until" sortable column on the definitions table, a "Muted until" field in the create/edit dialog, and a "Muted" chip in the instance triggers table.

**Choices to review**

- **`mute` is on the shared `SignalFilterAction` enum.** Instance `filter_action` and `SignalFilter.action` use the same enum, so a filter definition can now be created with `action: mute`. It does nothing. I left that alone, but it's a footgun. Rejecting it in `SignalFilterBase` is a small follow-up.
- **Timezone-aware column.** `expiration` is a naive column, but a naive string sent for `muted_until` would be read in the server's timezone. I used the tz-aware `date-time-picker-menu` (already used for `resolve_by`) rather than `ExpirationInput`, whose `toLocalISOString` sends a naive string.

**Verification**

- New tests: `test_filter_actions_mute`, `test_filter_actions_mute_expired`, `test_filter_actions_mute_skips_deduplication`, `test_update__muted_until`, and `test_signal_instance_create_flow_muted_signal_opens_no_case`.
- `tests/signal`: 37 passed, 1 skipped.
- Full suite: 364 passed, 8 failed, 4 skipped. The failures are 6 in `tests/ai/test_ai_service.py`, `tests/database/test_service.py::test_restricted_case_filter_with_test_data`, and `tests/entity/test_entity_service.py::test_find_entities_with_field_only`. They fail the same way on a clean checkout of HEAD.
- `ruff check` passes on the Python changes. Some existing lines in those files were already not `ruff format`-clean, and I left them alone.

**Not verified**

- I did not run the Alembic migration against a live Postgres. I checked only that it is the single head.
- I did not run the Vue UI in a browser, so the column and dialog are unexercised.
- During the full-suite run, I briefly ran `git stash` in the working tree. That run was stale, so I restarted it. The stash popped cleanly and the diff is intact.