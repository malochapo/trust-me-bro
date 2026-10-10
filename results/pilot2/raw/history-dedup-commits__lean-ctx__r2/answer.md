Four commits since 2025-05-22 changed the snooze and dedup decision logic. All four touch `src/dispatch/signal/service.py`, where `filter_snooze` and `filter_dedup` live.

- **a348bbd2** (2025-05-29), "don't dedup on canary signals": signal instances that are canary signals are no longer deduplicated.
- **7a9fe810** (2025-06-19), "make the default deduplication window configurable": the default dedup window now comes from `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`. This is the commit that changed the window itself.
- **086dc910** (2025-08-07), "simplify snooze filter checks": a refactor of the snooze filter checks.
- **917a0b7b** (2025-08-14), "share the lookback window computation": this adds the shared `_window_start()` helper. The default dedup window and the `SignalFilter.window` value (stored in seconds) both use it.

The last two are refactors, but they rewrote the snooze and window-calculation code, so I included them.

I left out several commits whose messages mention signals, snoozing or dedup but which don't change this logic:

- **4474af25** only adds logging in `flows.py`.
- **d2675cf4** masks sensitive fields.
- **90f73fe2** and **50cf8979** fix or limit signal stats.
- **5e136d7b** and **01c28ff0** change UI pages.

I picked the four by checking the history of `service.py` and a pickaxe search (`-G`) for snooze, dedup and window terms across `src`. I didn't read the diffs of the two refactors line by line.

COMMITS: a348bbd2, 7a9fe810, 086dc910, 917a0b7b