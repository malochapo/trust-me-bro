Four commits since 2025-05-22 changed snooze or deduplication logic or its windows. I changed no code.

**Commits, oldest first** (all in `src/dispatch/signal/service.py`)

1. **`a348bbd2`** (2025-05-29, fix: don't dedup on canary signals)
   - `filter_dedup` returns early for canary instances, so they are never deduplicated and never serve as a dedup target.
   - Canary instances are also excluded from the candidate queries in both dedup paths.
   - No window changed.

2. **`7a9fe810`** (2025-06-19, make the default deduplication window configurable)
   - The default window for signals with no dedup filter was hard-coded to 1 hour.
   - It now comes from `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` in `src/dispatch/config.py:95`, default **45**, in **minutes**. Today that is 2700 seconds.

3. **`086dc910`** (2025-08-07, simplify snooze filter checks)
   - Snooze logic: the mode and action checks are merged into one condition. The "no mode" and "no action" warnings are gone.
   - Behavior change: an expired snooze filter used to `continue` to the next filter. It now `break`s out of the loop, so any later active snooze filter on the signal is skipped.
   - Snooze has no lookback window. It is governed by `SignalFilter.expiration`.

4. **`917a0b7b`** (2025-08-14, share the lookback window computation)
   - Adds `_window_start(seconds)`, which returns now minus the given seconds.
   - Per-filter dedup window: the code used to apply `timedelta(minutes=f.window)`. It now applies `_window_start(f.window)`, so the value is read as **seconds**. A filter's window is now 60 times shorter than before for the same stored number. The model says seconds (`src/dispatch/signal/models.py:206-208`), so this aligns the code with the model.
   - Default dedup window: now `_window_start(SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES * 60)`, which is the same 45 minutes.

**Windows as the code applies them today**

| Window | Value | Unit | Where |
|---|---|---|---|
| Default dedup (no dedup filters) | 45 (env `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`) | minutes, converted to 2700 s | `config.py:95`, `service.py` in `filter_dedup` |
| Per-filter dedup | `SignalFilter.window` | seconds | `service.py` `filter_dedup` |
| `SignalFilter.window` default, Pydantic schema | 600 | seconds (10 min) | `models.py:282` |
| `SignalFilter.window` default, DB column | 3600 | seconds (1 h) | `models.py:206-208` |
| Snooze | `SignalFilter.expiration` | absolute timestamp, no window | `filter_snooze` |

**Things to check**

- The `break` in `086dc910` may be unintended. Confirm whether an expired snooze should stop evaluation of the remaining filters.
- The `SignalFilter.window` default is 600 s in the schema and 3600 s in the column, so the value depends on whether a filter is created through the API or directly in the database.
- The docstring of `filter_signal` still says the default dedup window is 1 hour.
- I did not look at deployed data, so I cannot say whether existing per-filter windows were stored as minutes or seconds. If they were stored as minutes, the `917a0b7b` change shortens them 60-fold.

I excluded `5e136d7b` (snooze UI and schema field only) and `4474af25` (logging only), since neither changed the logic.

----- next turn -----

The cause was `917a0b7b` (refactor: share the lookback window computation, 2025-08-14). It made the per-filter window read `f.window` as seconds, where the original code read it as minutes. Your filter's stored 30 became 30 seconds, so two instances ten minutes apart fell outside the window and each opened a case. The UI labels the field "Window (minutes)" with options 5, 10, 15, 20, 30, so minutes is the intended meaning.

**Fix**

- `src/dispatch/signal/service.py`: `_window_start` now takes minutes. The per-filter window passes `f.window` directly, and the default dedup window passes `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` directly. The default still resolves to 45 minutes. The `filter_signal` docstring now gives the configured 45-minute default instead of "1-hour".
- `src/dispatch/signal/models.py`: the column comment now says minutes. The comment still said seconds and "1 hour", which is why the commit's author read it that way.
- No data migration is needed. Existing filters store minutes already, so they work without edits.

**Regression tests** (`tests/signal/test_signal_service.py`)

- `test_filter_actions_deduplicate_within_window_minutes`: window 30, instances 10 minutes apart. Expects deduplication.
- `test_filter_actions_deduplicate_outside_window_minutes`: window 30, instances 40 minutes apart. Expects no deduplication.

I confirmed the first test fails against the current HEAD `service.py` and passes with the fix. `python -m pytest tests/signal` gives 34 passed, 1 skipped. I ran only the signal tests, not the whole suite.

**Not changed, needs your decision**

- `086dc910` changed an expired snooze filter from `continue` to `break`. An expired snooze now stops evaluation of the remaining filters on that signal, so a later active snooze filter is skipped. This is not part of the window bug, so I left it. It looks unintended, and I can revert it on your word.
- The numeric defaults now read as minutes. `SignalFilter.window` defaults to 3600 in the DB column, which is 60 hours, and to 600 in the API schema, which is 10 hours. Both were written for seconds. Changing them alters behavior for filters created without a window, so I did not touch them.

----- next turn -----

The cause was `086dc910` (refactor: simplify snooze filter checks, 2025-08-07). In `filter_snooze`, an expired snooze filter used to `continue` to the next filter. The refactor changed that to `break`. When the expired filter came first, the loop exited before the valid filter was checked, so new instances for that user were not snoozed.

**Fix** (`src/dispatch/signal/service.py`)

- An expired snooze filter now `continue`s again, so the loop checks the remaining filters.

**Regression test** (`tests/signal/test_signal_service.py`)

- `test_filter_actions_snooze_after_expired_filter`: a signal has an expired snooze filter (7 days ago) listed first and a valid one (30 days ahead) listed second, both matching the same entity. The test expects the instance to be snoozed.
- It fails on the `break` code and passes with the fix.
- `python -m pytest tests/signal` gives 35 passed, 1 skipped. Ruff check and format are clean on the changed files.

**Still open**

- The earlier change to the window (the seconds-to-minutes fix) is unrelated to this report and is still in place.
- The numeric defaults for `SignalFilter.window` (3600 in the column, 600 in the schema) are still unresolved. They now read as minutes, which means 60 hours and 10 hours. I did not change them, because they affect filters created without an explicit window.

----- next turn -----

Recap of this session's changes, all uncommitted in the working tree:

- **Deduplication windows:** `917a0b7b` made per-filter dedup windows read minutes as seconds. Filters created in the UI were effectively 60 times shorter. The fix reads the window as minutes again, which matches the UI. Existing filters need no edits. The column comment now says minutes. A regression test covers a 30-minute window with instances 10 minutes apart.
- **Snoozing:** `086dc910` changed an expired snooze filter from `continue` to `break`, so a valid snooze filter listed after an expired one was never checked. The fix restores `continue`. A regression test covers an expired filter listed before a valid one.
- **Canary signals:** `a348bbd2` skips deduplication for canary signals. This was intended, and I did not change it.
- **Docs:** the `filter_signal` docstring now gives the configured default window instead of "1 hour".
- **Tests:** `python -m pytest tests/signal` gives 35 passed, 1 skipped.

Open items: the `SignalFilter.window` defaults (3600 in the column, 600 in the schema) now read as 60 hours and 10 hours. I did not change them.

DEDUP_WINDOW_BUG: 917a0b7b
SNOOZE_BUG: 086dc910
CANARY: a348bbd2
DEFAULT_WINDOW: 45 minutes
DEFAULT_WINDOW_SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES