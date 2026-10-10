Four commits since 2025-05-22 changed how Dispatch decides whether a new signal instance is snoozed or deduplicated. All four touch `src/dispatch/signal/service.py`.

- **a348bbd2** (`fix(signal): don't dedup on canary signals`): `filter_dedup` now returns early for canary instances. Canary instances are also excluded from the duplicate-matching queries.
- **7a9fe810** (`make the default deduplication window configurable`): the default dedup window was a hardcoded 1 hour. It is now `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`, which defaults to 45 minutes.
- **086dc910** (`simplify snooze filter checks`): this is labelled a refactor, but it changes behaviour in `filter_snooze`. An expired filter used to be skipped with `continue`, and now it ends the loop with `break`. The merged mode/action checks also stop logging warnings for filters with no mode or action.
- **917a0b7b** (`share the lookback window computation`): this is also labelled a refactor with a behaviour change. A filter's own `window` was previously treated as minutes. It is now treated as seconds, which shrinks the dedup window for filters that have one. The default window is unchanged.

I left out these signal commits because they don't affect the snooze or dedup decision:
- `4474af25`: adds outcome logging.
- `d2675cf4`: masks sensitive raw fields.
- `5e136d7b`: UI views.
- Other commits that only touch stats or tags.

COMMITS: a348bbd2, 7a9fe810, 086dc910, 917a0b7b