Four commits since 2025-05-22 changed how a new signal instance is snoozed or deduplicated. All four touch `src/dispatch/signal/service.py`, and one also touches `config.py`. I haven't changed any code.

**1. `a348bbd2` (2025-05-29), "fix(signal): don't dedup on canary signals" (#6026)**
- `filter_dedup` now returns right away if the incoming instance is a canary, so canaries are never deduplicated.
- Both dedup queries also exclude earlier canary instances (`~SignalInstance.canary`), so a canary can't become the case a new instance is attached to.
- This commit doesn't change any window.

**2. `7a9fe810` (2025-06-19), "feat(signal): make the default deduplication window configurable"**
- The window used when a signal has no filters at all was a hard-coded 1 hour. It now comes from the new `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` setting in `config.py`.
- The setting is an integer in minutes, read from the environment, with a default of **45 minutes**. The old behaviour was 60 minutes, so the default window got shorter.

**3. `086dc910` (2025-08-07), "refactor(signal): simplify snooze filter checks"**
- Two separate checks in `filter_snooze` (skip filters with no mode, skip filters with no action) are folded into one: `f.mode != active or f.action != snooze` means skip.
- A filter with no mode or no action is no longer logged with a warning. It is just skipped.
- An expired snooze filter now ends the loop (`break`) instead of moving on to the next filter (`continue`). So if a signal has an expired snooze filter, any snooze filters after it in the list are no longer checked. This is a real behaviour change in a commit labelled a refactor.
- Snooze has no window setting. It uses each filter's `expiration` timestamp, compared against the current UTC time.

**4. `917a0b7b` (2025-08-14), "refactor(signal): share the lookback window computation"**
- It adds a helper, `_window_start(seconds)`, that returns now (UTC) minus that many seconds. Both dedup paths use it.
- The no-filter default path passes `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES * 60`. That is still 45 minutes, so nothing changed there.
- The per-filter path used to subtract `f.window` as **minutes**. It now treats `f.window` as **seconds**. That is a real change in a commit labelled a refactor, and the new reading matches the model definition: `SignalFilter.window` is an integer number of seconds, default `60 * 60` (1 hour) in the database column. A filter whose `window` is 600 (the pydantic default) used to look back 600 minutes (10 hours) and now looks back 10 minutes. This commit is the one that fixes that unit mismatch.

**What the code applies today**

| Case | Window |
|---|---|
| Signal with no filters | 45 minutes by default (`SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`, configurable), applied as 2700 seconds |
| Signal with dedup filters | each filter's `window` in seconds (column default 3600, pydantic default 600) |
| Snooze | until the filter's `expiration` timestamp (no window) |

The `filter_signal` docstring still says the default grouping is a 1-hour window. That is out of date, since the default is now 45 minutes.

Other commits since that date touch the signal code (`4474af25`, `d2675cf4`, `5e136d7b`), but they don't change the snooze or dedup decision.

----- next turn -----

I saved the findings to memory, so a new session can pick them up. The note covers:

- the four commits (`a348bbd2`, `7a9fe810`, `086dc910`, `917a0b7b`);
- what each one changed;
- the window values and units the code applies today;
- the two behaviour changes hidden in "refactor" commits;
- the stale 1-hour docstring in `filter_signal`.

It also records that no code was changed.

----- next turn -----

The commit that broke it is `917a0b7b`, "refactor(signal): share the lookback window computation" (2025-08-14). The fix is in and the signal tests pass.

**Cause:** the refactor changed the per-filter lookback from `timedelta(minutes=f.window)` to seconds. It assumed the column held seconds, going by a misleading comment on `SignalFilter.window`. The UI offers "Window (minutes)" and saves minutes, so a window of 30 became 30 seconds. Two instances ten minutes apart were therefore never grouped.

**Correction to my earlier summary:** I said yesterday that `917a0b7b` made the window seconds, as if that were intended. That was wrong. The stored values are minutes, and the commit introduced the bug.

**Fix:**
- `src/dispatch/signal/service.py`: the filter window is now `_window_start(f.window * 60)`, so it is read as minutes again. Existing filters keep working with no data migration. I also corrected the stale "1-hour" default in the `filter_signal` docstring.
- `src/dispatch/signal/models.py`: the column comment now says minutes.
- `tests/signal/test_signal_service.py`: new `test_filter_actions_deduplicate_window_is_minutes`. It uses a window of 30 and an earlier instance ten minutes old, and expects the new instance to join its case. It fails without the fix.

One thing I left alone: the DB column default of 3600 and the pydantic default of 600 are now read as minutes, which is much longer than they look. Changing them would alter behaviour for existing rows, so say if you want that handled separately.

The canary commit is `a348bbd2`. It makes `filter_dedup` return early for canary instances and excludes canary instances from the dedup queries. The default window comes from `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`, which defaults to 45 (set in `src/dispatch/config.py`).

DEDUP_WINDOW_BUG: 917a0b7b0d2dccbfbd3dfd56b0f4453d8e22d771
CANARY: a348bbd2
DEFAULT_WINDOW: 45 minutes
DEFAULT_WINDOW_SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES