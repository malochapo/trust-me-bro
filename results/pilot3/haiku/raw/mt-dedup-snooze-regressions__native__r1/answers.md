Four commits since 2025-05-22 changed how Dispatch decides snooze or dedup, or the windows it uses. I changed no code.

**Current values, as the code applies them**

- **Default dedup window** (signal has no dedup filter): 45 minutes, which is 2700 seconds. It comes from `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` (`src/dispatch/config.py:95`), is read in minutes, and is converted with `* 60` in `filter_dedup`.
- **Custom dedup filter window** (`SignalFilter.window`): seconds. The DB column defaults to 3600 (`src/dispatch/signal/models.py:206`). The API schema defaults to 600 (`models.py:282`).
- **Snooze**: no lookback window. A snooze applies until its `expiration` timestamp.
- The `filter_signal` docstring still says the default window is 1 hour (`service.py` near line 873). That is stale; the code uses 45 minutes.

**Commits, oldest first**

1. **`a348bbd2`** (2025-05-29) — `fix(signal): don't dedup on canary signals (#6026)`. Canary incoming signals skip dedup entirely. Canary instances are excluded from match candidates in both the default and custom paths. The default window was hard-coded to 1 hour at this point.

2. **`7a9fe810`** (2025-06-19) — `feat(signal): make the default deduplication window configurable`. The hard-coded 1-hour default window became `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`, which defaults to 45. Deployments without the env var moved from 60 to 45 minutes.

3. **`086dc910`** (2025-08-07) — `refactor(signal): simplify snooze filter checks`. The separate mode and action checks merged into one condition. The "no mode" and "no action" warnings were removed; the comparisons still skip those filters. One real behavior change: an expired snooze filter used to `continue`, and now it `break`s. That stops the loop, so later active snooze filters on the same signal are no longer checked.

4. **`917a0b7b`** (2025-08-14) — `refactor(signal): share the lookback window computation`. It added `_window_start()`. Behavior changed in two places:
   - The default window is now `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES * 60` seconds. Same length as before.
   - The custom filter window changed unit. Before, `f.window` was passed as `timedelta(minutes=f.window)`; now it is treated as seconds. A stored 3600 used to mean 60 hours and now means 1 hour.

   The model comment already said seconds (since `ecbad47f`, 2022), so the commit aligns the code with the documentation. Any custom filters whose window was entered as minutes are now 60 times shorter. I did not check the existing data or the UI for how windows are entered. This is the change most worth verifying.

I also keyword-checked the diffs of `4474af25`, `5e136d7b` and `d2675cf4`. None touches the windows or the snooze/dedup decision logic; `4474af25` only adds outcome logging.

----- next turn -----

The cause is `917a0b7b` (`refactor(signal): share the lookback window computation`). The UI labels the window "Window (minutes)" and saves the raw number, so your filter's 30 is stored as `30`. Before that commit the code read it as 30 minutes. After it, the code reads it as 30 seconds, so two instances ten minutes apart never group.

**Fix**

- `src/dispatch/signal/service.py`: `_window_start` now takes minutes. Custom filter windows pass `f.window` directly. The default window passes `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` without the `* 60`. I also corrected the `filter_signal` docstring, which said 1 hour and now names the configured 45-minute default.
- `src/dispatch/signal/models.py`: the column comment now says minutes. The column default went from 3600 to 60 and the schema default from 600 to 10, so the defaults still mean one hour and ten minutes in the new unit.

**Existing filters:** the UI has always stored minutes, so existing filters behave as they did before `917a0b7b` without any edit or migration.

**Regression test:** `test_filter_actions_deduplicate_window_is_minutes` in `tests/signal/test_signal_service.py`. It creates an earlier instance 10 minutes old and a filter with `window=30`, then asserts the new instance is deduplicated. It failed on the unfixed code and passes now.

**Tests:** `python -m pytest tests/signal` gives 33 passed and 1 skipped (the skip was already there). I did not run the rest of the suite.

**Check before merging:** if any filter was created through the API with a seconds value on purpose, for example `window=600` meaning ten minutes, it now means ten hours. The UI never produces those values. I did not check production data, so it's worth a quick query for large window values.

I haven't committed anything.

----- next turn -----

The cause is `086dc910` (`refactor(signal): simplify snooze filter checks`). When a snooze filter had expired, the loop in `filter_snooze` went from `continue` to `break`. Expired filters that come before an active one therefore stop the loop, and the active snooze is never checked. That matches your report: the expired filter was listed first.

**Fix:** `src/dispatch/signal/service.py` now uses `continue` for an expired snooze filter, so later filters are still checked.

**Regression test:** `test_filter_actions_snooze_expired_filter_does_not_hide_active_snooze` in `tests/signal/test_signal_service.py`. It puts an expired filter (7 days ago) before an active one (30 days ahead) and asserts the instance is snoozed. The test failed on the code before the fix.

**Tests:** `python -m pytest tests/signal` gives 34 passed and 1 skipped. The skip was already there.

I haven't committed anything. The `window` fix from the previous report and this fix are both uncommitted in the working tree.

----- next turn -----

Changes made in this session, none committed yet:

- **Dedup windows:** custom filter windows were read as seconds instead of minutes, so a window of 30 grouped only 30 seconds of instances. `_window_start` now takes minutes, and the model's column default is 60 and schema default is 10. Existing filters work unchanged, since the UI has always stored minutes. Regression test: `test_filter_actions_deduplicate_window_is_minutes`.
- **Snoozing:** an expired snooze filter stopped the loop, so a valid snooze listed after it was never applied. Expired filters are now skipped with `continue`. Regression test: `test_filter_actions_snooze_expired_filter_does_not_hide_active_snooze`.
- **Verification:** `python -m pytest tests/signal` gives 34 passed and 1 skipped.
- **Stale docs:** the `filter_signal` docstring and the model comment now describe the minute units and the 45-minute default.

Note for the changelog: filters created through the API with a seconds value on purpose will now be 60 times longer. The UI never produces those.

DEDUP_WINDOW_BUG: 917a0b7b
SNOOZE_BUG: 086dc910
CANARY: a348bbd2
DEFAULT_WINDOW: 45 minutes
DEFAULT_WINDOW_SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES