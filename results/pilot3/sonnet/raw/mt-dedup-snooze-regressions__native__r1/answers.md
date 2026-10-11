Four commits since 2025-05-22 changed how Dispatch decides whether a new signal instance is snoozed or deduplicated. I read the diffs and the current code and ran nothing. The decision logic is in `src/dispatch/signal/service.py` (`filter_snooze`, `filter_dedup`, `filter_signal`).

**1. `a348bbd2` (2025-05-29), "fix(signal): don't dedup on canary signals" (#6026)**
- `filter_dedup` now returns early if the incoming instance is a canary, so canaries are never deduplicated.
- Both dedup queries, the default one and the per-filter one, now exclude existing canary instances with `~SignalInstance.canary`.
- This commit has no window change. The default window was still a hard-coded `timedelta(hours=1)`.

**2. `7a9fe810` (2025-06-19), "make the default deduplication window configurable"**
- The default window, used for signals with no filters at all, was hard-coded at 1 hour. It now comes from `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` in `config.py`.
- The default is **45 minutes**, not the old 1 hour, so the default behavior shortened from 60 to 45 minutes.
- The value is cast to an integer and applied as `timedelta(minutes=...)`.

**3. `086dc910` (2025-08-07), "simplify snooze filter checks"**
- The separate warn-and-skip checks for a missing `mode` and a missing `action` are folded into one condition. A filter is skipped unless it is active and its action is snooze.
- There is one behavior change. When a snooze filter has expired (`expiration <= now` in UTC), the loop now does `break` instead of `continue`. Any filters after the first expired snooze filter are no longer evaluated, including other snooze filters that may still be valid.
- Snooze has no lookback window. It depends on the filter's `expiration` datetime, which is compared in UTC.
- A filter with no expiration is logged and skipped.
- Snooze is still checked first, and dedup only runs if the instance wasn't snoozed.

**4. `917a0b7b` (2025-08-14), "share the lookback window computation"**
- It adds `_window_start(seconds)`, which returns now (UTC) minus `timedelta(seconds=seconds)`.
- The default dedup window is now computed as `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES * 60` seconds, which is the same 45 minutes as before.
- This one is a real behavior change for per-filter dedup. The code used to apply `f.window` as `timedelta(minutes=f.window)`. It now applies `f.window` as **seconds**.
  - The model column is documented as seconds, with a default of `60 * 60`, which is 1 hour. So the commit fixed a unit mismatch where the old code treated seconds as minutes.
  - The Pydantic schema default is `window: int | None = 600`, which is 10 minutes when read as seconds.
  - Any existing filter whose stored value was meant as minutes would now cover a much shorter span.

**Current effective windows**

| Case | Window |
|---|---|
| Snooze | No window. Active until the filter's `expiration`. |
| Dedup, signal with no filters | 45 minutes (configurable), matches the most recent non-canary instance that already has a case. |
| Dedup, signal with a dedup filter | `f.window` in seconds (model default 3600, schema default 600). It matches instances sharing entities and takes the earliest. |

The `filter_signal` docstring still says the default is a "1-hour window". That is stale, since the code uses 45 minutes by default.

Other commits in the range that touch signals, such as `4474af25` (logging), `d2675cf4` (masking raw fields) and `5e136d7b` (UI views), don't change the snooze or dedup logic.

----- next turn -----

`917a0b7b` ("share the lookback window computation", 2025-08-14) caused it. It changed per-filter dedup to read `SignalFilter.window` as seconds. The UI labels the field "Window (minutes)" and offers 5, 10, 15, 20 and 30, so a window of 30 became 30 seconds. Two instances ten minutes apart then fell outside the window and opened two cases.

**Fix**
- `src/dispatch/signal/service.py`: `_window_start` now takes minutes and subtracts `timedelta(minutes=...)`. The filter window is applied as minutes again, which is what the UI stores. Existing filters work without editing and no migration is needed.
- The default no-filter window (45 minutes) is now passed straight through, with no `* 60`, so it is unchanged at 45 minutes.
- `src/dispatch/signal/models.py`: the column comment wrongly said seconds, so I corrected it to minutes.

**Regression test**
`test_filter_actions_deduplicate_window_is_in_minutes` in `tests/signal/test_signal_service.py` models your case. An instance with a case exists from ten minutes ago, a dedup filter has window 30, and a new instance for the same entity must be deduplicated into that case. It fails on the old code and passes now, and `tests/signal` shows 33 passed and 1 skipped. I did not run the rest of the suite.

**Not changed**
- The column default is `60 * 60` and the schema default is `600`. Read as minutes, those are 60 hours and 10 hours, which look like leftovers from the seconds assumption. Before `917a0b7b` they were already being applied as minutes. I left them alone because changing them would alter behavior for filters created through the API without a window. Say if you want them set to saner values.
- The `filter_signal` docstring still says the default window is 1 hour. The code uses 45 minutes.

I haven't committed anything.

----- next turn -----

The cause is `086dc910` ("simplify snooze filter checks", 2025-08-07), which I listed earlier. In `filter_snooze`, it turned the `continue` after an expired filter into `break`. The loop therefore stopped at the first expired snooze filter and never reached the valid one. For "Okta: Impossible travel", the filter that expired last week hid the one valid until next month, so new instances weren't snoozed.

**Fix:** in `src/dispatch/signal/service.py` I changed that `break` back to `continue`, so an expired filter is skipped and the remaining filters are still checked. The `break` after an actual snooze match stays, since that one is correct.

**Regression test:** `test_filter_actions_snooze_expired_then_valid` in `tests/signal/test_signal_service.py`. The signal has two snooze filters on the same entity, one expired 7 days ago and one valid for 30 more days, and the new instance must be snoozed. With `break` restored the test fails. With `continue` it passes, and `tests/signal` shows 34 passed and 1 skipped.

Nothing is committed. The uncommitted changes also include the window fix from the previous task.

----- next turn -----

**Recap**

Two regressions came from refactors in August 2025, and both are now fixed in the working tree (nothing committed).

- **Dedup windows:** `917a0b7b` changed per-filter dedup to read `SignalFilter.window` as seconds. The UI stores minutes, so a window of 30 acted as 30 seconds and instances ten minutes apart opened separate cases. `_window_start` now takes minutes again, and the stale column comment is corrected. Regression test: `test_filter_actions_deduplicate_window_is_in_minutes`.
- **Snoozing:** `086dc910` turned the `continue` after an expired snooze filter into `break`, so one expired filter stopped the loop before a still-valid one was checked. It is `continue` again. Regression test: `test_filter_actions_snooze_expired_then_valid`.
- **Canary signals:** `a348bbd2` made `filter_dedup` return early for canary instances and excluded existing canary instances from both dedup queries. This was intended behavior and is unchanged.
- **Default window:** `7a9fe810` made the window for signals without filters configurable and changed it from 1 hour to 45 minutes. The `filter_signal` docstring still says 1 hour, which is stale.
- **Left alone:** the column default (`60 * 60`) and schema default (`600`) for `window` are now read as minutes, which looks odd. I did not change them.

`tests/signal` passes with 34 passed and 1 skipped. I did not run the rest of the suite.

DEDUP_WINDOW_BUG: 917a0b7b
SNOOZE_BUG: 086dc910
CANARY: a348bbd2
DEFAULT_WINDOW: 45 minutes
DEFAULT_WINDOW_SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES