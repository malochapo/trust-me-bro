No code was changed. Four commits since 2025-05-22 touch the snooze or dedup decision (all in `src/dispatch/signal/service.py`, plus config for one). Two of them change behavior that matters for the windows.

**Commits, oldest first**

1. **`a348bbd2`** (2025-05-29) *fix(signal): don't dedup on canary signals (#6026)*
   - Canary instances skip deduplication entirely. The default path and the custom-filter path both exclude canary instances from the pool of instances they match against.
   - No time window involved.

2. **`7a9fe810`** (2025-06-19) *feat(signal): make the default deduplication window configurable*
   - Added `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` in `src/dispatch/config.py`, default `45`.
   - Previously the default window was hard-coded to 1 hour. It is now 45 minutes, overridable by env var.

3. **`086dc910`** (2025-08-07) *refactor(signal): simplify snooze filter checks*
   - Merged the mode and action checks in `filter_snooze` into one condition. This removed the "has no mode" and "has no action" warnings.
   - Behavior change: an expired snooze filter used to `continue`, so later snooze filters were still checked. It now `break`s, so no later snooze filter is evaluated once an expired one is hit.

4. **`917a0b7b`** (2025-08-14) *refactor(signal): share the lookback window computation*
   - Added `_window_start(seconds)`, which both dedup paths now use.
   - Behavior change: custom dedup filter windows were read as **minutes** (`timedelta(minutes=f.window)`). They are now read as **seconds** (`_window_start(f.window)`, with the comment "SignalFilter.window is stored in seconds"). No migration accompanied this, so existing filters' values are reinterpreted, not converted.

**Windows as the code applies them today**

| Window | Value and unit | Where |
|---|---|---|
| Default dedup (signal has no filters) | `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` = 45 min, converted to **2700 s** | `service.py` `filter_dedup`, via `config.py` |
| Custom dedup filter | `SignalFilter.window`, read as **seconds** | `service.py` `filter_dedup` |
| Custom filter default (Pydantic schema) | 600 **s** (10 min) | `signal/models.py` `SignalFilterBase` |
| Custom filter default (DB column) | 3600 **s** (1 h) | `signal/models.py` `SignalFilter.window` |
| Snooze | No window. Active until `expiration` passes | `filter_snooze` |

**Mismatch to know about:** the filter dialog still labels the field "Window (minutes)" and offers 5, 10, 15, 20, 30 (`src/dispatch/static/dispatch/src/signal/filter/SignalFilterCreateDialog.vue:56-57, 196`). It sends the raw number without converting. So a filter a user creates as "30 minutes" now dedups over 30 seconds. Filters created before `917a0b7b` were meant as minutes and are now 60× shorter. I did not check the production database, so I can't say how many filters are affected.

**Other notes**
- The `filter_signal` docstring still says the default dedup window is "1-hour", which is stale.
- `src/dispatch/signal/flows.py` has a 5-second threshold (`time_since_last_update >= timedelta(seconds=5)`) in the Slack update path. It decides whether to post an update for a deduplicated signal, not whether the instance is deduplicated, so I left it out.
- `4474af25` (logging) and `5e136d7b` (UI) changed no decision logic, so I left them out.

----- next turn -----

The bug came from `917a0b7b` (2025-08-14, "refactor(signal): share the lookback window computation"). It changed the deduplication lookback to read `SignalFilter.window` as seconds, but the UI and existing rows store minutes. So a window of 30 became 30 seconds, and two instances ten minutes apart never grouped. I don't have yesterday's list, so I rebuilt the candidates from git history since 2025-05-22 by searching the signal code for dedup, snooze, window and canary changes.

**Fix**
- `src/dispatch/signal/service.py`: the lookback now converts minutes to seconds (`_window_start(f.window * 60)`), so existing filters work without edits.
- `src/dispatch/signal/models.py`: the column comment and default now say minutes (`default=60`, still one hour). No migration is needed because the stored values were already minutes.
- `filter_signal`'s docstring said the default window was one hour; it now names the setting.

**Tests**
- Added `test_filter_actions_deduplicate_window_in_minutes`: a window-30 filter groups two instances ten minutes apart. It fails on the buggy line and passes with the fix.
- Added `test_filter_actions_deduplicate_window_expired_in_minutes`: an instance 40 minutes old is outside a 30-minute window and is not grouped.
- `python -m pytest tests/signal`: 34 passed, 1 skipped. I did not run the full suite. Ruff isn't installed here, so I didn't lint.

**Things I left alone**
- `SignalFilterBase.window` in `models.py` still defaults to `600`, which is now 600 minutes for API-created filters that omit a window. It predates the bug and matches the stored unit, but you may want it lower.
- The canary behaviour is unchanged. Canary instances are excluded from deduplication by `a348bbd2` ("fix(signal): don't dedup on canary signals", 2025-05-29), which is the commit for the canary line below.

DEDUP_WINDOW_BUG: 917a0b7b
CANARY: a348bbd2
DEFAULT_WINDOW: 45 minutes
DEFAULT_WINDOW_SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES