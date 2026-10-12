Four commits since 2025-05-22 changed how a new signal instance is snoozed or deduplicated. Two of them change the time windows. I made no code changes.

**Commits (oldest first)**

1. **`a348bbd2`** (2025-05-29), *fix(signal): don't dedup on canary signals (#6026)*
   - Canary instances skip deduplication entirely, and canary instances are excluded from the candidate set when looking for a match.
   - No window involved.

2. **`7a9fe810`** (2025-06-19), *feat(signal): make the default deduplication window configurable*
   - Adds `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` in `src/dispatch/config.py:95`, read from the environment with a default of 45.
   - The default-dedup path (used when a signal has no filters) previously looked back `timedelta(hours=1)`. It now looks back 45 minutes.

3. **`086dc910`** (2025-08-07), *refactor(signal): simplify snooze filter checks*
   - Merges the mode and action checks in `filter_snooze` into one condition. The missing-mode and missing-action warnings are removed.
   - Behavior change: when a snooze filter has expired, the loop now `break`s instead of `continue`ing. Any later active snooze filters in the list are no longer checked for that signal. This may be intentional, but it is a behavior change and I did not find a note explaining it.

4. **`917a0b7b`** (2025-08-14), *refactor(signal): share the lookback window computation*
   - Adds `_window_start(seconds)` and passes it both the default window and the per-filter window.
   - Behavior change: `SignalFilter.window` used to be applied as minutes (`timedelta(minutes=f.window)`). It is now applied as seconds. A filter with `window=600` used to look back 10 hours and now looks back 10 minutes. I found no data migration for the stored values in the history I searched.

**Current windows as the code applies them**

- Snooze: no window. A snooze applies while `expiration` is in the future, and an expression is optional.
- Default dedup (signal has no filters): 45 minutes, which is 2700 seconds in code (`signal/service.py:805`, `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES * 60`).
- Per-filter dedup: `SignalFilter.window` in seconds (`signal/service.py:845-846`). The model default is 3600 seconds, a comment on `signal/models.py:206-208` says 1 hour, and the Pydantic schema default is 600 seconds (`signal/models.py:282`).

**Excluded:** `dee1699d`, `5e136d7b`, and the Slack/UI commits matched on incidental words, not on the dedup/snooze logic.

**Limits of the search:** I searched `src/dispatch/signal/`, `plugins/`, `config.py`, `extensions.py`, `case/messaging.py`, and `project/models.py` for the words snooze, dedup, window, and timedelta. Commits that changed dedup logic under other paths would not appear.

----- next turn -----

I saved the findings in two places so you can pick them up tomorrow.

- **Memory file:** `memory/signal-snooze-dedup-history.md` under the project memory directory. It lists the four commits, what each changed, the current window values, the search limits, and the two items most likely to need a decision (`917a0b7b` and `086dc910`).
- **Memory index:** `memory/MEMORY.md` did not exist, so I created it with one pointer line to that file.
- **sobre session:** I also recorded a finding in the sobre session with the same commits and current values.

The memory file's line numbers are from the current checkout. Re-check them with git before relying on them tomorrow. I made no code changes.

----- next turn -----

The deduplication bug came from `917a0b7b` (2025-08-14, "refactor(signal): share the lookback window computation"). It changed how `SignalFilter.window` is read from minutes to seconds. The UI still stores minutes ("Window (minutes)", values 5–30), so a filter set to 30 was looking back 30 seconds. The two GuardDuty instances ten minutes apart fell outside that window and each opened a case.

**Fix**
- `src/dispatch/signal/service.py`: `_window_start` now takes minutes. The per-filter path passes `f.window` directly, and the default path passes `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`. Existing filters keep their stored values and are read as minutes, so nothing needs editing.
- `src/dispatch/signal/models.py`: the column default is now `60` (minutes) instead of `60 * 60`, and the schema default is `60` instead of `600`. The schema default changed value, so API clients that omit `window` will now get one hour instead of 600 minutes. I chose 60 to match the one-hour intent in the comment; say if you want a different default.
- `tests/signal/test_signal_service.py`: added `test_filter_actions_deduplicate_window_is_minutes`. It creates an instance ten minutes old, a filter with `window=30`, and asserts the new instance joins that case. It fails on the old code and passes with the fix.

`python -m pytest tests/signal` passes (33 passed, 1 skipped).

**Scope**: I only ran the signal tests. I did not run the full suite.

**Canary commit**: `a348bbd2` (2025-05-29, "fix(signal): don't dedup on canary signals"). It was not part of this bug and is unchanged.

**Default window**: signals with no filters use 45 minutes, set by `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` in `src/dispatch/config.py`.

DEDUP_WINDOW_BUG: 917a0b7b
CANARY: a348bbd2
DEFAULT_WINDOW: 45 minutes
DEFAULT_WINDOW_SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES