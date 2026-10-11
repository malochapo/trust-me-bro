Four commits since 2025-05-22 changed how Dispatch decides snooze or dedup, and one of them silently changed a time window's units. I made no code changes.

**Commits, oldest first**

1. **`a348bbd2`** (2025-05-29, Will Sheldon), *fix(signal): don't dedup on canary signals*. Canary instances skip `filter_dedup` entirely, and canary instances are excluded from the candidate queries in both dedup paths. Snooze still applies to canaries. `filter_signal` runs before the canary early return in `flows.py`, so canaries do reach the snooze check.

2. **`7a9fe810`** (2025-06-19, Jordan Lee), *make the default deduplication window configurable*. For signals with no dedup filters, the window was hard-coded at 1 hour. It now comes from `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` (env var, default `45`, in minutes) and is applied as `minutes * 60` seconds.

3. **`086dc910`** (2025-08-07, Sam Ortega), *simplify snooze filter checks*. The mode/action checks were merged into one `continue`, and the missing-mode/missing-action warnings were removed. The behavior change is that an expired snooze filter now hits `break` instead of `continue`, so the loop stops at the first expired snooze filter and never evaluates later snooze filters. This is the one change to snooze decisions.

4. **`917a0b7b`** (2025-08-14, Jordan Lee), *share the lookback window computation*. This added `_window_start(seconds)` and moved both windows onto it. The per-filter dedup window was `timedelta(minutes=f.window)` and is now `_window_start(f.window)`, with a comment saying it is stored in seconds. That is a real behavior change under a refactor label: a filter's `window` now means seconds, so an existing value of `N` looks back `N` seconds instead of `N` minutes, 60× narrower. Existing stored values were not migrated.

**Windows as the code applies them today**

- **Default dedup window** (signals with no dedup filters): `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`, default 45 minutes, applied as 2700 seconds.
- **Per-filter dedup window** (`SignalFilter.window`): seconds. The column default is 3600 (1 hour), set in 2023. The API schema default is 600 seconds (10 minutes), set 2025-05-07, which is before your cutoff.
- **Snooze**: no lookback window. It uses the filter's `expiration` timestamp.

**Excluded:** `4474af25` (2025-06-10) only adds logging. `d2675cf4` (2025-07-03) redacts raw fields before entity extraction, which changes dedup inputs but not the dedup or snooze logic itself. Other signal-area commits in the range don't touch these paths.

**Stale comment:** the `filter_signal` docstring (`service.py`, around line 869) still says the default dedup window is 1 hour, but it is 45 minutes.

----- next turn -----

The window now means minutes again, so a filter set to 30 deduplicates against instances up to 30 minutes old. The cause was `917a0b7b` (2025-08-14, Jordan Lee, "share the lookback window computation"). It changed the per-filter window from `timedelta(minutes=f.window)` to seconds, so a 30 became a 30-second lookback. The UI labels the field "Window (minutes)" with options 5–30 and sends the value unconverted, so existing stored values are already minutes and needed no migration.

**Changes**
- `src/dispatch/signal/service.py`: `_window_start` now takes minutes. The filter window and the default dedup window (`SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`) both pass minutes, so the `* 60` conversion is gone. I also corrected the `filter_signal` docstring, which still said "1-hour window".
- `src/dispatch/signal/models.py`: the column comment now says minutes.
- `tests/signal/test_signal_service.py`: added `test_filter_actions_deduplicate_window_is_minutes`, parametrized with a window of 30:
  - a prior instance 10 minutes old is deduplicated;
  - one 45 minutes old is not.

I confirmed the test catches the bug: with the seconds line restored, the 10-minute case fails. The first version of the test passed under the bug, so I rewrote it to isolate each case.

**Tests:** `python -m pytest tests/signal` gives 34 passed, 1 skipped (was 32 passed, 1 skipped; the two new parametrized cases account for the difference). I did not run the full suite. `ruff` isn't installed here, so I didn't lint.

**Not changed, for you to decide**
- `SignalFilter.window` column default is still `60 * 60`. In minutes that is 60 hours, not the 1 hour its old comment claimed. It only applies when a row is inserted without a window; the API schema always supplies one. Changing it would be a behavior change, so I left it.
- The API schema default (`SignalFilterBase.window = 600`) is now 600 minutes, about 10 hours. That matches how the code treated it before `917a0b7b`, so I left it.
- Separate from this bug: `086dc910` still changes snooze behavior. An expired snooze filter now stops the loop (`break`), so later active snooze filters are never checked. I didn't touch that.

Nothing is committed.

----- next turn -----

The cause is `086dc910` (2025-08-07, Sam Ortega, "simplify snooze filter checks"). It changed the expired-filter branch in `filter_snooze` from `continue` to `break`. When the expired filter came first in the loop, the loop stopped there, so the valid filter after it was never checked and the instance was not snoozed.

**Fix:** `src/dispatch/signal/service.py` now uses `continue` for expired snooze filters, so the loop moves on to the next filter. This is the only code change in this round.

**Regression test:** `test_filter_actions_snooze_expired_then_active` in `tests/signal/test_signal_service.py`. It sets an expired snooze filter (7 days ago) ahead of a valid one (30 days out) on the same entity, and asserts the instance is snoozed. With `break` restored, the test fails; with the fix, it passes.

**Results:** `python -m pytest tests/signal` gives 35 passed, 1 skipped.

Nothing is committed. The window-unit fix from the previous round is still uncommitted in the same working tree, along with this one.

----- next turn -----

Recap of this round:

- **Deduplication windows** (`917a0b7b`): the per-filter dedup window was read as seconds instead of minutes, so a filter set to 30 looked back 30 seconds. The fix makes `_window_start` take minutes, which matches the UI's "Window (minutes)" field and the default-window config. Existing filters need no edits. A regression test covers a prior instance 10 minutes old (deduplicated) and one 45 minutes old (not).
- **Snoozing** (`086dc910`): an expired snooze filter stopped the loop with `break`, so a valid snooze filter listed after it was never checked. The fix uses `continue`. A regression test covers an expired filter followed by a valid one on the same entity.
- **Canary signals** (`a348bbd2`): canary instances no longer go through deduplication and are excluded from the candidate matches. Snoozing still applies to them.
- **Signal tests:** `python -m pytest tests/signal` gives 35 passed, 1 skipped.
- **Not committed:** all changes are in the working tree. The window fix also changed a stale comment in `models.py` and a docstring in `service.py`.

DEDUP_WINDOW_BUG: 917a0b7b
SNOOZE_BUG: 086dc910
CANARY: a348bbd2
DEFAULT_WINDOW: 45 minutes
DEFAULT_WINDOW_SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES