Signal filters now have an optional `reason`, stored in the database and accepted and returned by the filters API. The web UI shows it as a Reason column in the Snoozes table and has a Reason field in the create-filter dialog. I didn't commit anything.

**Backend**
- `src/dispatch/signal/models.py`: added a nullable `reason` column to `SignalFilter`, and a `reason` field on `SignalFilterBase`. Create, update, and read schemas all inherit from that base, so the existing routes accept and return the field without changes.
- New migration `src/dispatch/database/revisions/tenant/versions/2026-10-10_fb54ca0f9f59.py` adds the column and revises `ff08d822ef2c`, the only head before this change. I picked the revision ID and date myself.

**Frontend**
- `filter/store.js`: `reason` is in the default selected state, so it's sent on create and update.
- `filter/SignalFilterCreateDialog.vue`: an optional auto-growing "Reason" textarea below Description on the Save step. It has no required rule.
- `instance/TableInstanceSnoozes.vue`: a "Reason" column between Description and Applies to.

**Tests**
- Added two tests to `tests/signal/test_signal_filter_service.py`: one creates a filter with a reason and checks it reads back through `SignalFilterRead`, and one updates the reason.
- `tests/signal`: 34 passed, 1 skipped.
- Full suite: 363 passed, 4 skipped, 6 failed. The 6 failures are all in `tests/ai/test_ai_service.py`, and they fail identically on the untouched tree, so they're not from this change.

**Not verified**
- I didn't run the migration against PostgreSQL. The test suite builds the schema from the models, so it doesn't exercise the migration. I confirmed by reading that the chain has a single head and the new revision sits on top of it.
- The frontend has no `node_modules` here, so I couldn't run prettier, eslint, or a build. The Vue changes follow the surrounding code's patterns, but they haven't been compiled or rendered.