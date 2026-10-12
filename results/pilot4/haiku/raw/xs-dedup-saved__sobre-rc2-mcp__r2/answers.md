Four commits since 2025-05-22 changed snooze or dedup decisions. The most important is `917a0b7b`, which changed the per-filter window from minutes to seconds without migrating stored values. The UI still labels that field "Window (minutes)", so 5–30 minute windows now apply as 5–30 seconds. I changed no code.

**Commits, oldest first**

1. **`a348bbd2`** (2025-05-29), *fix(signal): don't dedup on canary signals*. Canary instances skip `filter_dedup` entirely. They are also excluded from the candidate queries for both the default and filter-based dedup. No window changed.

2. **`7a9fe810`** (2025-06-19), *make the default deduplication window configurable*. This applies to signals with no dedup filters. The window was hard-coded at 1 hour. It is now `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` (`src/dispatch/config.py:95`), default **45 minutes** (2700 s), and is applied as `minutes * 60` seconds. The docstring in `filter_signal` still says 1 hour.

3. **`086dc910`** (2025-08-07), *simplify snooze filter checks*. Two behaviour changes in `filter_snooze`:
   - An expired snooze filter used to `continue`, so later snooze filters were still checked. It now `break`s, so they are skipped.
   - Filters with a missing `mode` or `action` used to log a warning. They are now skipped silently.

4. **`917a0b7b`** (2025-08-14), *share the lookback window computation*. This is a refactor that changed the unit. The filter window was `timedelta(minutes=f.window)` and is now `_window_start(f.window)`, which treats it as **seconds**. The commit touches only `service.py` and adds no migration, so existing rows keep their numbers.

**Windows as the code applies them today**

- **Snooze:** no time window. A snooze lasts until its `expiration` timestamp.
- **Default dedup (no dedup filters):** 45 minutes by default, set by the environment variable.
- **Filter dedup:** `SignalFilter.window`, in **seconds**. The model default is 3600 (1 hour, `src/dispatch/signal/models.py:206`). The API schema default is 600 (10 minutes, `models.py:282`).
- **UI mismatch:** `SignalFilterCreateDialog.vue` offers `[5, 10, 15, 20, 30]` under a "minutes" label and sends the raw number. I found no conversion before save. A user who picks 30 minutes gets a 30-second window.

**Things I checked and excluded**

- `01c28ff0`, `5e136d7b`, `90f73fe2`, `dee1699d` changed only UI or stats code. Their `service.py` and `flows.py` diffs contain no snooze or dedup logic.
- `200cd428` is about case stable status. Its `timedelta` hits are unrelated.
- `flows.py:373` has a `timedelta(seconds=5)` check. It dates from 2023 and I did not assess it as part of the decision.

**Unverified**

- `SignalFilterBase.window` is typed `int | None`. If a null window reaches `filter_dedup`, `_window_start(None)` would raise a `TypeError`. I did not check whether the API rejects null windows.

----- next turn -----

I saved the findings to a memory file so tomorrow's session can pick them up. Nothing in the repo was changed.

The memory is `signal-snooze-dedup-history.md`, with a pointer in `MEMORY.md`. It records:

- **The four commits** that changed snooze or dedup logic since 2025-05-22: `a348bbd2`, `7a9fe810`, `086dc910`, `917a0b7b`.
- **The windows as they apply today:** the default dedup window is 45 minutes (env-configurable). Filter dedup windows are in seconds (DB default 3600, API default 600). Snooze has no window.
- **The main risk:** `917a0b7b` switched the filter window from minutes to seconds with no data migration. The UI still offers 5–30 under a "minutes" label and sends the raw value, so a 30-minute choice applies as 30 seconds.
- **Open items:** the stale "1-hour" docstring in `filter_signal`, whether a null window can crash `_window_start`, and whether stored windows need migrating.

The memory says to re-verify against the code before relying on it, since it came from a read-only history review.

----- next turn -----

The bug came from `917a0b7b` (refactor "share the lookback window computation", 2025-08-14). It changed the filter window from `timedelta(minutes=f.window)` to `_window_start(f.window)`, which treats the value as seconds. The UI still offers 5, 10, 15, 20 or 30 labelled "Window (minutes)", so a 30-minute filter became 30 seconds. Your two instances ten minutes apart fall outside that and open two cases.

**Fix**
- `src/dispatch/signal/service.py`: the filter window is converted from minutes to seconds before the lookback. Existing stored filters work unchanged because they already hold minute values from the UI. I also corrected the `filter_signal` docstring, which still said the default window was 1 hour; it is 45 minutes.
- `src/dispatch/signal/models.py`: the `SignalFilter.window` comment now says minutes, and the ORM default went from 3600 to 60 (still 1 hour).
- `tests/signal/test_signal_service.py`: two regression tests.
  - `test_filter_actions_deduplicate_window_is_minutes`: a window of 30 groups two instances ten minutes apart. It fails on the old code and passes now.
  - `test_filter_actions_deduplicate_window_excludes_older_instances`: an instance 40 minutes old is outside a 30-minute window. This one passed on the old code too, so it checks the upper bound only.

**Tests**
- `tests/signal`: 34 passed, 1 skipped.
- Full suite: 8 failed, 361 passed, 4 skipped. I checked the failing tests on a clean tree: six AI tests and the two tests in `tests/database/test_service.py` and `tests/entity/test_entity_service.py` also fail there. These failures predate my change.

**Decisions for you**
- The API schema default for `SignalFilterBase.window` is still `600`. Under minutes that is 10 hours, not the 10 minutes the old comment implied. I left it alone because it changes behavior for API clients that omit `window`. Say if you want it set to 10.
- Filters created through the API after 2025-08-14 with a value meant as seconds will now widen to minutes. Those can't be told apart from UI filters, so I didn't migrate anything.
- Nothing is committed.

DEDUP_WINDOW_BUG: 917a0b7b
CANARY: a348bbd2
DEFAULT_WINDOW: 45 minutes
DEFAULT_WINDOW_SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES

----- next turn -----

That notification is for the background wait I already finished. Nothing new came out of it, and the work is unchanged: the fix and the two regression tests are in the working tree, uncommitted.