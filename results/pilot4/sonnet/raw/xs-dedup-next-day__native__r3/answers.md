Four commits since 2025-05-22 changed how Dispatch decides whether a new signal instance is snoozed or deduplicated. All the code is in `src/dispatch/signal/service.py` (`filter_snooze` and `filter_dedup`), plus `src/dispatch/config.py` for one of them. I read the diffs but did not run anything.

**1. `a348bbd2` (2025-05-29, #6026), "don't dedup on canary signals"**
- `filter_dedup` now returns immediately if the incoming instance is a canary.
- Both dedup queries (the default one and the per-filter one) now exclude canary instances with `~SignalInstance.canary`, so canaries never match as the earlier instance.
- It did not change any window. The default window was still a hard-coded `timedelta(hours=1)`.

**2. `7a9fe810` (2025-06-19), "make the default deduplication window configurable"**
- The default dedup window replaced the hard-coded 1 hour. It applies to signals that have no filters at all.
- It now comes from the new `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` setting in `config.py`.
- The setting is an int in minutes and defaults to **45 minutes**. So the default dropped from 60 to 45 minutes.
- The docstring of the function that calls `filter_dedup` (`filter_signal`) still says "1-hour window". That text is out of date.

**3. `086dc910` (2025-08-07), "simplify snooze filter checks"**
- This is mostly a refactor. It removed the separate "no mode" and "no action" warnings and merged the checks into `f.mode != active or f.action != snooze`.
- It also made one behaviour change: when a snooze filter has expired (`expiration <= now`, compared in UTC), the code now does `break` instead of `continue`. An expired snooze filter now stops the loop, so any later snooze filters on that signal are no longer checked. This is probably unintended.
- Snoozing has no lookback window. The only time value is the filter's `expiration` timestamp. A filter with no expiration is skipped with a warning.

**4. `917a0b7b` (2025-08-14), "share the lookback window computation"**
- It added a `_window_start(seconds)` helper that returns `now(UTC) - timedelta(seconds=seconds)`.
- The default dedup window is now `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES * 60`, which is 2700 seconds. That is the same 45 minutes as before.
- This one changes behaviour for filter-based dedup. `f.window` used to be treated as **minutes** (`timedelta(minutes=f.window)`). It is now treated as **seconds** (`_window_start(f.window)`).
  - The model column comment says the window is in seconds, with a default of `60 * 60` (1 hour). The pydantic schema default is `600`, which is 10 minutes in seconds.
  - Before this commit, those stored values would have been read as minutes. A default of 600 would have meant 600 minutes.
  - Existing filters now get a much shorter lookback than they did before this commit.

**How it works today**
- Snooze runs first. If the instance is snoozed, dedup is skipped.
- With no filters on the signal, the instance joins the most recent non-canary instance that already has a case, created within the last 45 minutes (configurable).
- With filters, each active dedup filter uses its own `window` in seconds. The default is 3600 in the model and 600 in the schema. A matching instance in that window must share an entity and satisfy the filter expression. The instance joins the earliest such instance's case.

----- next turn -----

Commit 917a0b7b ("refactor(signal): share the lookback window computation") caused the bug. It changed the filter window from minutes to seconds, so a window of 30 became 30 seconds. The UI field is labelled "Window (minutes)" and offers 5, 10, 15, 20 or 30, and the code before that commit used minutes.

**Fix:** in `src/dispatch/signal/service.py`, `_window_start` now takes minutes. Filter windows are read as minutes again, so existing filters work without edits. The default no-filter window passes its minutes value straight through, without the `* 60` that the refactor added.

**Test:** `test_dedup_filter_window_is_in_minutes` in `tests/signal/test_signal_service.py` uses a 30-minute filter and an instance for the same entity created 10 minutes earlier. It checks that a new instance is deduplicated into the existing case. It fails without the fix and passes with it. All of `tests/signal/test_signal_service.py` passes (15 passed, 1 skipped); I did not run the rest of the suite.

**Left alone:** the `window` column in `src/dispatch/signal/models.py` has a comment saying "seconds" and a default of 3600, which is inconsistent with minutes. That comment is probably what misled the refactor. I didn't change the default, because that would change behavior for filters that don't set a window.

DEDUP_WINDOW_BUG: 917a0b7b
CANARY: a348bbd2
DEFAULT_WINDOW: 45 minutes
DEFAULT_WINDOW_SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES