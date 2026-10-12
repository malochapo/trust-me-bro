Four commits since 2025-05-22 changed how Dispatch decides whether a new signal instance is snoozed or deduplicated, or the windows it uses. No code was changed. I read the code and the commit diffs, but did not run anything.

**Commits, oldest first**

1. **`a348bbd2`, 2025-05-29, "fix(signal): don't dedup on canary signals"**
   - Canary instances skip deduplication entirely (`filter_dedup` returns early).
   - Canary instances are also excluded as dedup targets in both the default and filter-based queries.
   - Snooze is not changed, so canary instances can still be snoozed.

2. **`7a9fe810`, 2025-06-19, "feat(signal): make the default deduplication window configurable"**
   - The default window for signals with no dedup filter was hard-coded to 1 hour. It is now `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` (`src/dispatch/config.py:95`), default **45 minutes**, read in minutes and multiplied by 60 in `service.py`.
   - Net effect: the default window dropped from 60 to 45 minutes unless the env var is set.

3. **`086dc910`, 2025-08-07, "refactor(signal): simplify snooze filter checks"**
   - Not just a refactor. An expired snooze filter used to `continue` to the next filter. It now `break`s, so the first expired snooze filter stops evaluation of any remaining snooze filters.
   - The removed `mode`/`action` None checks have no behaviour change; a None value already fell through to `continue`.

4. **`917a0b7b`, 2025-08-14, "refactor(signal): share the lookback window computation"**
   - Also a behaviour change labelled as a refactor. `SignalFilter.window` was used as **minutes** (`timedelta(minutes=f.window)`). It is now used as **seconds** (`_window_start(f.window)`).
   - Existing deduplicate filters now look back 60× less far than before.

**Windows as the code applies them today**

- **Snooze:** no time window. A snooze filter applies until its `expiration` datetime passes. Filters with no expiration are skipped with a warning.
- **Deduplication with no dedup filter on the signal:** 45 minutes by default (`SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`, in minutes), computed as `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES * 60` seconds.
- **Deduplication with a dedup filter:** `SignalFilter.window`, in **seconds**.
  - The database column defaults to 3600 seconds (`src/dispatch/signal/models.py:206`).
  - The API schema defaults to 600 seconds (`models.py:282`).

**Mismatch to be aware of**

The filter creation dialog (`src/dispatch/static/dispatch/src/signal/filter/SignalFilterCreateDialog.vue:56,196`) labels its window "Window (minutes)" with choices 5, 10, 15, 20, 30. The value is sent to the API unchanged, so a "10 minute" choice is stored as 10 and applied as **10 seconds**. This follows from reading the code, not from running it.

**Other notes**

- The `filter_signal` docstring still says the default is a "1-hour window"; it is now 45 minutes by default.
- Signals that have any dedup filter never fall back to the default 45-minute window.

I also recorded these findings with `sobre_session`, as the CLAUDE.md instructions ask.

----- next turn -----

The audit is saved so tomorrow's session can pick it up. No code was changed.

- **Memory file:** `signal-snooze-dedup-windows.md` in the project memory directory. It has the four commits (`a348bbd2`, `7a9fe810`, `086dc910`, `917a0b7b`), the windows as the code applies them today, and the open issues.
- **Index:** a one-line pointer in `MEMORY.md`.
- **Session record:** the same findings were already recorded with `sobre_session` earlier.

The two open items to check first tomorrow:

1. The filter dialog labels its window choices (5–30) as minutes, but the backend reads them as seconds.
2. `917a0b7b` and `086dc910` were labelled refactors but changed behaviour. The memory file says to re-verify the code before acting on any of this, in case it has moved.

----- next turn -----

The deduplication window bug was caused by `917a0b7b` ("refactor(signal): share the lookback window computation", 2025-08-14). It is not a behaviour-preserving refactor. Before it, `filter_dedup` subtracted `f.window` as minutes. After it, the value is passed as seconds, so a window of 30 looks back 30 seconds. The UI offers 5–30 labelled "minutes" and sends them unconverted, so the 10-minute pair fell outside the window and opened two cases.

**Fix**
- `src/dispatch/signal/service.py`: `filter_dedup` now uses `_window_start(f.window * 60)`, so a filter's window is in minutes, as the UI says. Existing filters need no edits, since their stored numbers already meant minutes.
- `src/dispatch/signal/service.py`: the `filter_signal` docstring now gives the default window as 45 minutes instead of the stale "1-hour".
- `src/dispatch/signal/models.py`: the `SignalFilter.window` column default is now 60 (minutes), and the API schema default is now 10 (minutes). The old values, 3600 and 600, would have meant 60 hours and 10 hours under the minutes unit.
- `tests/signal/test_signal_service.py`: new `test_filter_actions_deduplicate_window_is_minutes`. It creates an instance 10 minutes earlier and a window of 30, then expects deduplication. It fails on the original code and passes with the fix.

**Tests:** `tests/signal` passes (15 passed, 1 skipped), and `tests/signal` plus `tests/case` passes (48 passed, 1 skipped), run with `python -m pytest`.

**Caveat:** any filter created through the API after `917a0b7b` with a seconds-sized value, such as 600 or 3600, will now look back that many minutes. I could not tell those apart from UI-created filters, so check for them if any exist.

I did not change the UI, since it already labels and sends minutes. The `break` change in `086dc910` is a separate behaviour change, and I left it alone. The memory file's open issue about the minutes/seconds mismatch is now resolved in code, but I did not update the memory file.

DEDUP_WINDOW_BUG: 917a0b7b
CANARY: a348bbd2
DEFAULT_WINDOW: 45 minutes
DEFAULT_WINDOW_SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES