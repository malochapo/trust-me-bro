Four commits since 2025-05-22 changed how Dispatch decides whether a new signal instance is snoozed or deduplicated, or changed the windows it uses. I haven't changed any code.

**Commits, oldest first**

1. **`a348bbd2`** (2025-05-29, fix): canary signals are no longer deduplicated. Canary instances are skipped in `filter_dedup`, and they are excluded from the candidate set for both the default path and filter-based dedup. No window changed.

2. **`7a9fe810`** (2025-06-19, feat): the default dedup window, used when a signal has no dedup filters, is now read from `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` in `config.py`. The commit message says the window was "hard-coded", but it also changed the value from 60 minutes to 45 minutes.

3. **`086dc910`** (2025-08-07, refactor): snooze checks were simplified in `filter_snooze`. Two things changed behavior, though the commit message doesn't mention either:
   - An expired snooze filter now `break`s the loop instead of `continue`-ing. Later snooze filters on the same signal are no longer evaluated once an expired one is reached.
   - The warnings for filters with no mode or no action were removed. Those filters are still skipped, just silently.

4. **`917a0b7b`** (2025-08-14, refactor): the lookback window is now computed by `_window_start(seconds)`. Per-filter `SignalFilter.window` changed from minutes (`timedelta(minutes=f.window)`) to seconds. No migration or data conversion came with it, so existing filter rows are now read as seconds. A window that was 10 minutes is now 10 seconds.

**Values the code applies today**

| Mechanism | Window | Unit | Source |
|---|---|---|---|
| Default dedup (signal has no dedup filters) | 45 minutes (2700 s) | minutes, env-configurable | `config.py`, `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`, default 45 |
| Per-filter dedup | `SignalFilter.window` | seconds | `signal/models.py` |
| Per-filter default, Pydantic schema | 600 s (10 min) | seconds | `SignalFilterBase.window` |
| Per-filter default, DB column | 3600 s (1 hour) | seconds | `SignalFilter.window` column default |
| Snooze | none | n/a | Snooze is active until the filter's `expiration` timestamp passes. A snooze filter without an expiration is skipped. |

**Things to be aware of**
- The docstring of `filter_signal` and the comment in `tests/signal/test_signal_service.py` still say "1-hour" for the default dedup window. The code uses 45 minutes.
- The tests create dedup filters with `window=5`. Under the current seconds unit that is 5 seconds, which may not be what those tests intend.
- The 5-second check in `flows.py` (`timedelta(seconds=5)`) decides whether to post a Slack update for a deduplicated signal. It is not part of the dedup decision, and it predates 2025-05-22 (`a643cd11`, 2023), so I left it out.

**Checked and excluded**
- `dee1699d`: report-button visibility, not snooze or dedup.
- `4474af25`: adds logging of each signal's filter outcome, no decision change.
- `d2675cf4`, `5e136d7b`: no snooze or dedup changes.

----- next turn -----

The regression came from `917a0b7b` (2025-08-14, "share the lookback window computation"). It changed per-filter windows from minutes to seconds. The UI labels the field "Window (minutes)" and offers 5–30, so a window of 30 was read as 30 seconds. The other commits don't explain this: `7a9fe810` only affects signals with no dedup filter. Nothing is committed yet.

**Fix**
- `src/dispatch/signal/service.py`: `_window_start` now takes minutes, and a filter's `window` is interpreted as minutes again. The default dedup window passes `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` directly, without the `* 60`.
- `src/dispatch/signal/models.py`: the column default is 60 and the schema default is 10, with comments saying minutes. These match the windows that new filters get today (1 hour and 10 minutes), so the only change is the unit label. The `filter_signal` docstring now refers to the configurable default instead of "1-hour".
- Existing filters need no edits or migration. UI-created filters store the value the user picked, which is already in minutes.

**Regression test**
- `test_filter_actions_deduplicate_window_is_minutes` in `tests/signal/test_signal_service.py`. It has a window of 30 and two prior instances: one 40 minutes old, which is outside the window, and one 10 minutes old, which is inside it. A new instance should join the 10-minute-old instance's case. It failed before the fix and passes now.
- I also corrected the stale "1-hour" comment in an existing test.

**Results**
- `python -m pytest tests/signal`: 33 passed, 1 skipped.
- Full `python -m pytest`: 360 passed, 4 skipped, 8 failed. The 8 failures are in `tests/ai/test_ai_service.py`, `tests/database/test_service.py::test_restricted_case_filter_with_test_data`, and `tests/entity/test_entity_service.py::test_find_entities_with_field_only`. They fail the same way on unmodified `HEAD`, which I checked in a temporary worktree that I've since removed. They're unrelated to this change, so I left them alone.
- `ruff check` passes on the changed signal files.

**Data caveat:** The API accepts raw integers, and the UI only offers minute values. Any filter created through the API between 2025-08-14 and this fix with a value meant as seconds (for example, 600) will now be read as minutes and become a much wider window. The UI-created ones are fine. Please check whether any API clients set windows in that period.

----- next turn -----

The cause is `086dc910` (2025-08-07, "simplify snooze filter checks"). It's from the same batch as the window change, but it's a separate commit. That commit changed the expired-snooze branch in `filter_snooze` from `continue` to `break`. When the first snooze filter on a signal had expired, the loop stopped there and never checked the valid filter after it. That's why the "Okta: Impossible travel" instances weren't snoozed. Nothing is committed yet.

**Fix:** in `src/dispatch/signal/service.py`, the expired branch goes back to `continue`, so expired filters are skipped and later ones are still evaluated. I left the rest of that commit's simplification alone, since it doesn't change behavior.

**Regression test:** `test_filter_actions_snooze_expired_before_active` in `tests/signal/test_signal_service.py`. It lists a snooze filter that expired seven days ago before a snooze filter valid for thirty days, both matching the same entity. The instance should be snoozed. It failed before the fix and passes now.

**Results:** `python -m pytest tests/signal` gives 34 passed, 1 skipped, and `ruff check` passes. I didn't rerun the full suite after this change. The earlier full run had 8 failures in the AI, database, and entity tests that also fail on unmodified `HEAD`. This fix only touches `filter_snooze`, so I don't expect them to change.

----- next turn -----

Recap of this session's changes (all uncommitted in the working tree):

- **Deduplication windows:** Commit `917a0b7b` read per-filter `window` values as seconds instead of minutes, so a 30-minute window became 30 seconds. Fixed in `src/dispatch/signal/service.py` by reading the window as minutes again. Model defaults in `src/dispatch/signal/models.py` are now 60 and 10 minutes. Regression test: `test_filter_actions_deduplicate_window_is_minutes`.
- **Snoozing:** Commit `086dc910` changed an expired snooze filter from `continue` to `break`, which stopped evaluation before later valid filters. Fixed by restoring `continue`. Regression test: `test_filter_actions_snooze_expired_before_active`.
- **Canary signals:** Commit `a348bbd2` stopped canary signals from being deduplicated. No change here.
- **Default grouping window:** Commit `7a9fe810` made the default window configurable. Its default is now 45 minutes, down from the earlier hard-coded 1 hour.

Tests: `python -m pytest tests/signal` passes (34 passed, 1 skipped). The full suite has 8 failures in the AI, database, and entity tests that also fail on unmodified `HEAD`.

```
DEDUP_WINDOW_BUG: 917a0b7b
SNOOZE_BUG: 086dc910
CANARY: a348bbd2
DEFAULT_WINDOW: 45 minutes
DEFAULT_WINDOW_SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES
```