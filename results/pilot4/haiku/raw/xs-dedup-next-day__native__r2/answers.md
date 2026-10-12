Four commits since 2025-05-22 changed how Dispatch decides whether a new signal instance is snoozed or deduplicated. Only one of them, `917a0b7b`, changed a time window's unit, and that change is silent. I didn't change any code.

**Commits**

1. **`a348bbd2`** (2025-05-29), *fix(signal): don't dedup on canary signals*. Canary instances are never deduplicated, and canary instances are excluded as dedup targets in both the default and the filter-based paths. Snooze is unaffected.
2. **`7a9fe810`** (2025-06-19), *make the default deduplication window configurable*. The window for signals with no dedup filter was hard-coded to 1 hour. It now comes from `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`, which defaults to 45.
3. **`086dc910`** (2025-08-07), *simplify snooze filter checks*. Two behavior changes:
   - An expired snooze filter now ends the loop with `break`, where it used to be `continue`. Later active snooze filters on the same signal are no longer evaluated after an expired one.
   - The "has no mode" and "has no action" warnings were removed.
4. **`917a0b7b`** (2025-08-14), *share the lookback window computation*. The per-filter `SignalFilter.window` used to be treated as minutes (`timedelta(minutes=f.window)`). It is now treated as seconds, through the shared `_window_start()` helper. The commit adds a comment saying the value is in seconds, but it has no data migration. Existing filters therefore went from 10 hours to 10 minutes at a stored value of 600, a 60× shrink. Nothing else in the commit changed.

**Current windows, as the code applies them**

| Setting | Value | Unit | Where |
|---|---|---|---|
| Per-filter dedup `window` (API/Pydantic default) | 600 | seconds (10 min) | `signal/models.py:282` |
| Per-filter dedup `window` (DB column default) | 3600 | seconds (1 h) | `signal/models.py:206-208` |
| Default dedup window (no dedup filter) | 45 | minutes (2700 s), set by `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` | `config.py:95-96`, `signal/service.py:805` |
| Snooze | no time window; the filter has an absolute `expiration` datetime | — | `signal/service.py:743-781` |

The default window only matches instances that already have a case. It attaches the new instance to the most recent match's case.

**Things to know**

- The 600-second Pydantic default and the 3600-second column default disagree. The column comment still says "default to 1 hour".
- The `filter_signal` docstring still says "1-hour window", which predates `7a9fe810`.
- I did not check whether the UI sends a `window` value. `filter/store.js` defaults it to `null`, and I did not read the filter create dialog.
- The 5-second check in `signal/flows.py:373` throttles Slack updates for deduplicated instances. It doesn't affect the dedup decision, so I left it out.
- `4474af25` only adds logging of each instance's outcome, so it is not included.

----- next turn -----

The cause is commit `917a0b7b` ("refactor(signal): share the lookback window computation", 2025-08-14). The UI offers 5–30 and stores that number as-is, and the code treated it as minutes until that commit. The commit switched the filter path to `timedelta(seconds=f.window)`, so a window of 30 became 30 seconds. Two instances ten minutes apart therefore never matched.

I don't have yesterday's list in this conversation, so I rebuilt it from `git log --since=2025-05-22` on the signal code. The dedup and snooze changes are `a348bbd2`, `7a9fe810`, `4474af25`, `086dc910` and `917a0b7b`. Only `917a0b7b` changed how a filter's window is computed.

**Fix**
- `src/dispatch/signal/service.py`: the filter path now converts minutes to seconds (`_window_start(f.window * 60)`). Existing filters need no edits, since their stored values are already minutes. The default-window path was never broken.
- `src/dispatch/signal/models.py`: the column comment now says minutes. I also changed the Python-side default from 3600 to 60, since 3600 would have meant 60 hours under the minutes convention. No migration is needed because it is not a server default.
- `filter_signal`'s docstring said the default window was 1 hour; it now points at the setting.

**Regression tests** (`tests/signal/test_signal_service.py`)
- `test_filter_window_is_in_minutes`: window 30, instance from 10 minutes ago, expects deduplication. It failed before the fix and passes now.
- `test_filter_window_short_does_not_match_older_instance`: window 5, same instance, expects no match. This guards the unit from the other side.

`python -m pytest tests/signal` gives 34 passed, 1 skipped. I did not run the full suite.

**Found but not fixed:** `086dc910` changed `continue` to `break` in `filter_snooze` for expired snooze filters. An expired snooze now stops evaluation of every later snooze filter on the signal, so a later active snooze can be missed. The fix is a one-word change back to `continue`. I left it alone because you asked about dedup windows; say the word and I'll make it.

DEDUP_WINDOW_BUG: 917a0b7b
CANARY: a348bbd2
DEFAULT_WINDOW: 45 minutes
DEFAULT_WINDOW_SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES