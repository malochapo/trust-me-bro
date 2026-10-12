Four commits since 2025-05-22 changed how Dispatch decides whether a new signal instance is snoozed or deduplicated. I haven't changed any code. The logic is in `src/dispatch/signal/service.py`, in `filter_snooze`, `filter_dedup` and `_window_start`.

**Windows as the code applies them today**
- **Default dedup window:** 45 minutes, applied as `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES * 60` seconds (`config.py:95`). It is used only when the signal has no filters at all.
- **Per-filter dedup window:** `SignalFilter.window` is read as seconds. The model comment says "number of seconds … default to 1 hour", and the default is `60 * 60` = 3600 s (`models.py:206`). The Pydantic schema default is 600 s (`models.py:282`).
- **Snooze:** there is no lookback window. A snooze filter has an `expiration` timestamp. The instance is snoozed only while `expiration` is later than now in UTC.

**Commits**
1. `a348bbd2` (2025-05-29), "fix(signal): don't dedup on canary signals (#6026)":
   - `filter_dedup` now returns immediately for a canary instance.
   - Both dedup queries (the default one and the per-filter one) now exclude canary instances with `~SignalInstance.canary`.
   - It also rewrote `tests/signal/test_signal_service.py`.
   - It did not change any window.
2. `7a9fe810` (2025-06-19), "make the default deduplication window configurable":
   - The default window had been hard-coded as `timedelta(hours=1)`.
   - It now reads the new `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` setting, which defaults to 45. This is the only commit that changed the default window's value, from 60 to 45 minutes.
3. `086dc910` (2025-08-07), "simplify snooze filter checks":
   - It removed the "no mode" and "no action" warnings and merged the mode and action checks into one condition.
   - **Behaviour change:** when a snooze filter has expired, the loop now does `break` instead of `continue`. An expired snooze filter therefore stops the evaluation of any later filters. The commit message doesn't mention this.
4. `917a0b7b` (2025-08-14), "share the lookback window computation":
   - It added `_window_start(seconds)`, which returns now (UTC) minus that many seconds.
   - The default window now goes through it as `MINUTES * 60`, which gives the same result as before.
   - **Behaviour change:** the per-filter window used to be `timedelta(minutes=f.window)`. It is now `_window_start(f.window)`, so `f.window` is treated as seconds. That matches the model's comment and default, but a stored value that was meant as minutes now covers a 60× shorter lookback. For example, 60 used to mean 1 hour and now means 1 minute. The commit is labelled a refactor and doesn't mention this.

Other commits in the range, such as `d2675cf4` (masking raw fields) and `4474af25` (outcome logging), touch signal processing but don't change the snooze or dedup decision.

I checked the diffs of all four commits and the current code. I did not run the tests.

----- next turn -----

**Cause:** commit `917a0b7b` ("refactor(signal): share the lookback window computation"). Before it, `filter_dedup` used `timedelta(minutes=f.window)`. The refactor moved to a `_window_start(seconds)` helper and passed `f.window` straight in, with a comment saying the value is in seconds. But the UI's "Window (minutes)" picker (5–30) stores minutes, and existing rows hold minutes. So a window of 30 became 30 seconds, and two instances ten minutes apart no longer matched.

**Fix** (`src/dispatch/signal/service.py`): `filter_dedup` now calls `_window_start(f.window * 60)`, so the stored value is read as minutes again. No data migration is needed and existing filters work unedited. I also corrected the `SignalFilter.window` column comment and default in `models.py`. The default was `60 * 60` "seconds", and it is now `60` minutes, which is still one hour. That default only applies to newly created rows, so no migration is needed there either.

**Regression test:** `test_filter_actions_deduplicate_window_is_in_minutes`. It uses a `window=30` filter with instances 40 and 10 minutes old, and expects the new instance to dedupe into the 10-minute-old one's case. It fails on the old code and passes now. The full `tests/signal` run gives 33 passed and 1 skipped.

**Related bug, not fixed:** `086dc910` changed `continue` to `break` on an expired snooze filter in `filter_snooze`. One expired snooze filter now stops the loop, so any later snooze filters on that signal are never checked. I left it alone since you didn't ask for it.

I didn't commit anything.

DEDUP_WINDOW_BUG: 917a0b7b0d2dccbfbd3dfd56b0f4453d8e22d771
CANARY: a348bbd267238b110a5d25fabb1e4e2380630831
DEFAULT_WINDOW: 45 minutes
DEFAULT_WINDOW_SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES