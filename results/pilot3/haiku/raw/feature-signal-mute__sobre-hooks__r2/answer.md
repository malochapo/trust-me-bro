Muted signal definitions now record their new instances with the `mute` filter action and open no case. The mute ends on its own when `muted_until` passes. The 50 signal and case tests pass, including three new ones; I did not run the migration against a live database or open the UI in a browser.

**What changed**

- **Database:** `Signal.muted_until` is a nullable datetime, stored as naive UTC like `SignalFilter.expiration`. The migration is `src/dispatch/database/revisions/tenant/versions/2026-10-11_49e6c960943c.py`, chained after the current head `ff08d822ef2c`.
- **API:** `muted_until` is on the shared signal schema, so create, update and read all carry it. Timezone-aware input is converted to naive UTC. An explicit `null` clears the mute; omitting the field leaves it unchanged.
- **Filtering:** `filter_signal` in `src/dispatch/signal/service.py` checks `is_muted` first. A muted signal gets `filter_action = mute`, and snooze and dedup are skipped. The existing flow already stops case creation when `filter_signal` returns True.
- **Web UI:** `Table.vue` has a "Muted until" column, formatted with the existing `formatDate` helper. `NewEditDialog.vue` sets the value with the existing `ExpirationInput` component, labelled "Muted until"; the default state is in `store.js`.

**Choices you may want to change**

- `mute` is added to the shared `SignalFilterAction` enum, so it is also a valid value for `SignalFilter.action`. A signal filter with `action: mute` has no effect, because only snooze and dedup filters are evaluated. Rejecting it in the filter schema would be a small follow-up.
- The filter-action dropdown in the UI doesn't list `mute`, since mute is set on the definition, not on a filter.
- The history log doesn't record mute changes. `update()` skips datetime fields when it builds the change log, and `expiration` has the same gap. Fixing it means special-casing `muted_until` there.

**Tests added** (`tests/signal/test_signal_service.py`)

- A muted signal with a matching snooze filter gets the `mute` action and no case.
- An expired mute behaves as if unset.
- Timezone normalization and the null-clears / omitted-keeps behavior on create and update.

**Checks not run**

- Prettier and ESLint on the Vue files: prettier flags `Table.vue` and `store.js`, but HEAD already fails the same check, so I left that alone. I did not run ESLint.
- Ruff flags `models.py`, but HEAD has the same formatting issue at the end of the file, so I left it.