Four commits since 2025-05-22 changed the snooze/dedup decision or its windows. All changes are in `src/dispatch/signal/service.py`, and I didn't modify anything.

**1. `a348bbd2`, 2025-05-29: fix(signal): don't dedup on canary signals**
- `filter_dedup` returns early for canary instances, so they are never deduplicated.
- Canary instances are also excluded from the candidate pool in both dedup queries (the default-window query and the per-filter query).
- No window values changed.

**2. `7a9fe810`, 2025-06-19: make the default deduplication window configurable**
- The default window for signals with no dedup filter was hard-coded to 1 hour. It is now `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` in `src/dispatch/config.py`, read as an int with a default of **45 minutes**.
- Unit: minutes, set by the env var.

**3. `086dc910`, 2025-08-07: refactor(signal): simplify snooze filter checks**
- The snooze checks were merged into one condition: `mode != active or action != snooze` → skip.
- The warnings for a missing mode or action were removed. Both columns are non-nullable, so this shouldn't change results.
- Behavior change: when a snooze filter's expiration has passed, the loop now `break`s instead of `continue`ing. Snooze filters after an expired one are no longer checked. Before this commit, they were.
- Snooze has no window. It uses only the filter's `expiration` timestamp.

**4. `917a0b7b`, 2025-08-14: refactor(signal): share the lookback window computation**
- Added `_window_start(seconds)`.
- Default dedup window: `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES * 60` seconds, so still **45 minutes** by default.
- Per-filter dedup window: `SignalFilter.window` is now treated as **seconds**. Before this commit, it was `timedelta(minutes=f.window)`. The column has documented seconds since `ecbad47f` (2022), so this aligned the code with the model. Existing filters' effective windows shrink by 60×, and I found no data migration in the commits since the cutoff that rescales stored values.
- The model default is 3600 seconds (1 hour). The Pydantic schema default is 600.

**Current values as the code applies them:**
- Snooze: no window; active until `expiration`.
- Default dedup (no dedup filters): 45 minutes (`SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`, overridable by env var).
- Per-filter dedup: `SignalFilter.window` seconds, with the DB default 3600 s and the schema default 600 s.

Other commits in the range (`5e136d7b`, `d2675cf4`, `4474af25`, `01c28ff0`) touched the UI, redaction, or logging, not the snooze/dedup logic.

----- next turn -----

**Cause:** commit `917a0b7b` (2025-08-14, "share the lookback window computation"). It changed the per-filter dedup window from `timedelta(minutes=f.window)` to `timedelta(seconds=f.window)`. The UI labels the field "Window (minutes)" and offers 5–30, and the value is saved as entered. So a filter set to 30 was treated as 30 seconds, and two instances ten minutes apart fell outside it and opened separate cases. The model comment said "seconds," but nothing in the UI or stored data does.

**Fix:** the window is minutes again, which is what the UI and existing filters already mean.
- `src/dispatch/signal/service.py`: `_window_start` takes minutes. The per-filter window and the default dedup window (`SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`, 45) both use it, with no `* 60`.
- `src/dispatch/signal/models.py`: the column comment now says minutes. The Python-side default changed from `60 * 60` to `60`, and the Pydantic default from `600` to `60`, so "default to 1 hour" still holds. This is a Python default, not a server default, so no migration is needed.
- Existing filters need no edits. Their stored values were already minutes, so they behave as they did before `917a0b7b`.

**Regression tests** (`tests/signal/test_signal_service.py`):
- `test_filter_actions_deduplicate_window_is_minutes`: a 30-minute filter groups an instance created 10 minutes earlier. This fails with the seconds behavior and passes with the fix.
- `test_filter_actions_deduplicate_window_outside_minutes`: an instance 40 minutes earlier is not grouped by a 30-minute filter.

**Tests:** the signal suite passes (34 passed, 1 skipped). The full suite has 8 failures in `tests/ai/test_ai_service.py`, `tests/database/test_service.py`, and `tests/entity/test_entity_service.py`. The same 8 fail on untouched `HEAD`, so they predate this change and I didn't touch them.

**Not changed:**
- `086dc910` changed the expired-snooze branch from `continue` to `break`. Expired snooze filters now stop the loop, so later snooze filters on that signal are never checked. It is unrelated to windows, but it may be a second behavior regression, so it's worth a look.
- A dedup filter with a NULL window still raises a `TypeError` in `_window_start`. That predates this change, and I didn't add a fallback.

----- next turn -----

**Cause:** commit `086dc910` (2025-08-07, "simplify snooze filter checks"). When a snooze filter's expiration had passed, the loop in `filter_snooze` changed from `continue` to `break`. The `break` ends the whole loop, so any valid snooze filter listed after an expired one was never checked. For the "Okta: Impossible travel" signal, the expired filter came first, so new instances for that user were not snoozed.

**Fix:** `src/dispatch/signal/service.py` line 763 is back to `continue`. An expired filter is skipped and the loop moves on to the next one.

**Regression test:** `test_filter_actions_snooze_expired_before_valid` in `tests/signal/test_signal_service.py`. It lists a snooze filter that expired seven days ago before one that is valid for 30 days, and asserts that the instance is snoozed. It fails before the fix and passes after.

**Tests:** the signal suite passes (35 passed, 1 skipped). The full suite gives 8 failed, 362 passed, 4 skipped. The same 8 failures (AI service, database, and entity tests) also fail on untouched `HEAD`, so they predate these changes.

Across the two reports, the working tree now has three fixes: the minutes window in `917a0b7b` (with the default-value changes in `models.py`), the `break` in `086dc910`, and their regression tests. Nothing is committed.

----- next turn -----

Recap of the three fixes in the working tree, none committed yet:

- **Deduplication windows** (`917a0b7b`): the per-filter window was read as seconds instead of minutes, so a 30-minute filter only grouped instances within 30 seconds. It now reads minutes again, which matches the UI and existing filters. Regression test: `test_filter_actions_deduplicate_window_is_minutes`.
- **Snoozing** (`086dc910`): an expired snooze filter ended the loop with `break`, so valid snooze filters listed after it were never checked. It now uses `continue`. Regression test: `test_filter_actions_snooze_expired_before_valid`.
- **Canary signals** (`a348bbd2`): this commit is the one that made canary signals skip deduplication. I did not change it.

Changelog entries:

DEDUP_WINDOW_BUG: 917a0b7b0d2dccbfbd3dfd56b0f4453d8e22d771
SNOOZE_BUG: 086dc910c308c8e5a91f5be8b4624cce11feae85
CANARY: a348bbd267238b110a5d25fabb1e4e2380630831
DEFAULT_WINDOW: 45 minutes
DEFAULT_WINDOW_SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES