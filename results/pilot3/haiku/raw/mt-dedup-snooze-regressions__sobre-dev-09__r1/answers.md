Five commits since 2025-05-22 changed the snooze/dedup decision or its windows. I made no code changes.

**Commits (oldest first)**

1. **`a348bbd2`** (2025-05-29), *fix(signal): don't dedup on canary signals*. `filter_dedup` returns early for canary instances, and canary instances are excluded from the match queries in both the default and filter-based paths. Snooze is not affected. No window change.

2. **`7a9fe810`** (2025-06-19), *make the default deduplication window configurable*. Added `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` in `src/dispatch/config.py:95`, read as an int from the environment with default 45. The default-window path in `filter_dedup` moved from a hard-coded 1 hour to this setting. The per-filter window was still interpreted as minutes at this point.

3. **`086dc910`** (2025-08-07), *simplify snooze filter checks*. Merged the mode/action checks into one condition and removed the "no mode" and "no action" warnings. Behaviour change: an expired snooze filter now `break`s out of the loop instead of `continue`ing, so any later snooze filters on that signal are no longer evaluated.

4. **`917a0b7b`** (2025-08-14), *share the lookback window computation*. Added `_window_start(seconds)`. Per-filter `SignalFilter.window` is now treated as **seconds**, where it was previously minutes. A filter window of 10 used to mean 10 minutes and now means 10 seconds. The default path was converted to `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES * 60`, so its effective value is unchanged.

5. **`dee1699d`** (2025-08-15) touches project and UI code for report suggestions and does not affect snooze or dedup. `4474af25` only adds logging of the outcome.

**Windows and units as the code applies them today**

- **Snooze:** no time window. A snooze filter applies while `expiration` is in the future; an expired or missing expiration means it is skipped (`src/dispatch/signal/service.py`, `filter_snooze`).
- **Default dedup** (only when the signal has no filters at all): `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`, default **45 minutes** (2700 seconds). A signal with filters but no deduplicate filter gets no default dedup.
- **Per-filter dedup:** `SignalFilter.window`, in **seconds**.
  - The database column defaults to 3600 (1 hour), `src/dispatch/signal/models.py:206`.
  - The pydantic `SignalFilterBase` default is 600 (10 minutes), `models.py:282`.
  - The filter dialog offers 5, 10, 15, 20, 30 under the label "Window (minutes)" (`src/dispatch/static/dispatch/src/signal/filter/SignalFilterCreateDialog.vue:56,196`). The backend reads those numbers as seconds, so a user selecting "10 minutes" gets a 10-second window. I did not trace the save payload end to end, so this is inferred from the code I read.

**Other things I noticed**

- The `filter_signal` docstring still says the default window is 1 hour; the code uses 45 minutes unless overridden.
- The model comment says "1 hour", the column default is 3600 seconds, and the pydantic default is 600 seconds. These defaults disagree with each other.

----- next turn -----

The cause was `917a0b7b` (2025-08-14, *share the lookback window computation*). It changed the per-filter window from minutes to seconds, so a UI value of 30 became a 30-second window and your two instances, ten minutes apart, never grouped. `7a9fe810` only made the default window configurable and did not cause this.

**Fix**

- `src/dispatch/signal/service.py`: `_window_start` takes minutes again, so `SignalFilter.window` means minutes as the UI says. The default path passes `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` directly, which keeps the 45-minute default. I kept the helper from the refactor and fixed the docstring that still said "1-hour window".
- `src/dispatch/signal/models.py`: the column comment now says minutes, and the column default and the pydantic default both changed to `60` (1 hour). The old defaults were 3600 and 600, which read as 60 hours and 10 hours under minutes.

Existing filters work without edits: the values stored for UI-created filters (5–30) are already minutes.

**Regression test**

`tests/signal/test_signal_service.py::test_filter_actions_deduplicate_window_is_in_minutes` creates an instance from ten minutes ago with a case, adds a deduplicate filter with `window=30`, and asserts a new instance on the same entity is deduplicated into that case. It failed before the fix (`assert False`) and passes now.

**Test results**

- `python -m pytest tests/signal`: 33 passed, 1 skipped.
- I did not run the full suite.
- `ruff check` passes on the touched files. `ruff format` is clean for my edits; the one remaining diff is a blank line in `models.py` that was already there.

**Caveat for existing data**

Rows created before the fix by the API without a `window` have `600` stored, and rows created by the ORM default have `3600`. Those values now mean 600 and 3600 minutes, where before they meant 10 minutes and 1 hour. Filters created through the UI are not affected, since it always sends 5–30. I did not query the database, so you may want to check for rows with `window` in (600, 3600) that have no explicit window and set them by hand.

----- next turn -----

The cause was `086dc910` (2025-08-07, *simplify snooze filter checks*). It changed the expired-snooze branch in `filter_snooze` from `continue` to `break`. When a signal has an expired snooze filter listed before a valid one, the loop stops at the expired filter and never evaluates the valid one, so new instances for that user are not snoozed.

**Fix:** `src/dispatch/signal/service.py:763` now uses `continue` for an expired snooze filter, so the loop moves on to the next filter.

**Regression test:** `tests/signal/test_signal_service.py::test_filter_actions_snooze_after_expired_snooze` puts an expired snooze filter (7 days ago) ahead of a valid one (30 days out) that matches the entity, and asserts the instance is snoozed. I put the change in a temporary `break` and the test failed, then restored the fix.

**Test results:** `python -m pytest tests/signal` gives 34 passed, 1 skipped. `ruff check` and `ruff format --check` pass on the touched files. I did not run the full suite.

Both reports came from `086dc910`. Together with the window-unit change from `917a0b7b`, that makes two of the five commits from my first answer that caused regressions.

----- next turn -----

## Recap: signal deduplication and snoozing fixes

Three of the five commits since 2025-05-22 changed deduplication or snoozing in ways that broke filters. The other two (`dee1699d`, `4474af25`) don't affect those decisions.

- **`917a0b7b`** (2025-08-14) treated a filter's `window` as seconds instead of minutes. A UI window of 30 became 30 seconds, so instances ten minutes apart opened separate cases. Fixed by restoring minutes in `src/dispatch/signal/service.py` and changing the model defaults to 60 minutes in `src/dispatch/signal/models.py`. Filters created in the UI keep working without edits.
- **`086dc910`** (2025-08-07) changed the expired-snooze branch from `continue` to `break`. An expired snooze filter listed before a valid one stopped evaluation, so the valid one never applied. Fixed by restoring `continue`.
- **`a348bbd2`** (2025-05-29) made canary signals skip deduplication and excluded them from matching. This is intended behaviour, not a bug, and I did not change it.

Regression tests were added in `tests/signal/test_signal_service.py` for the window unit and for an expired snooze followed by a valid one. `python -m pytest tests/signal` gives 34 passed, 1 skipped. I did not run the full suite. The changes are uncommitted in the working tree.

Open item: rows already stored with `window` 600 or 3600 from API or ORM defaults now mean 600 or 3600 minutes, not seconds. I did not check the database for them.

DEDUP_WINDOW_BUG: 917a0b7b
SNOOZE_BUG: 086dc910
CANARY: a348bbd2
DEFAULT_WINDOW: 45 minutes
DEFAULT_WINDOW_SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES