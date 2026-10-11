Four commits since 2025-05-22 changed how Dispatch decides whether a new signal instance is snoozed or deduplicated. I changed no code. Snoozing is checked first, and dedup runs only if the instance wasn't snoozed.

**Time windows as the code applies them today:**
- **Default dedup window:** 45 minutes. This applies to signals with no filters at all. It comes from `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` (default `45`, in `src/dispatch/config.py`), and the code converts it to 2700 seconds.
- **Per-filter dedup window:** `SignalFilter.window`, an integer read as seconds. The model default is `60 * 60`, which is 3600 seconds or 1 hour. The pydantic schema default in `models.py:282` is 600 seconds, which is 10 minutes.
- **Snooze:** there is no lookback window. A snooze is active until the filter's `expiration` timestamp, compared in UTC.

**Commits:**
1. **`a348bbd2` (2025-05-29), "fix(signal): don't dedup on canary signals (#6026)"**
   - `filter_dedup` now returns early if the new instance is a canary.
   - Both the default dedup query and the per-filter query now exclude canary instances with `~SignalInstance.canary`, so canaries never count as the earlier instance to dedup against.
   - It also added tests.
2. **`7a9fe810` (2025-06-19), "make the default deduplication window configurable"**
   - The default window for signals without a dedup filter was hard-coded as `timedelta(hours=1)`.
   - It is now `timedelta(minutes=SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES)`, and the new config setting defaults to 45 minutes.
   - This changed the effective default from 60 to 45 minutes.
3. **`086dc910` (2025-08-07), "simplify snooze filter checks"**
   - It merged the separate mode and action checks in `filter_snooze` into one condition: skip any filter that isn't active or isn't a snooze.
   - It dropped the "no mode" and "no action" warnings.
   - An expired snooze filter now does `break` instead of `continue`, so the loop stops at the first expired snooze filter. Later snooze filters on the same signal are no longer checked, which could change behavior if filters are ordered with an expired one first.
4. **`917a0b7b` (2025-08-14), "share the lookback window computation"**
   - It added a `_window_start(seconds)` helper, and both dedup paths now use it.
   - The default path now uses `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES * 60`, which is still 45 minutes.
   - **Unit change:** the per-filter path used to be `timedelta(minutes=f.window)`. It is now `_window_start(f.window)`, with the comment "stored in seconds".
   - The column comment and default (`60 * 60`) do say seconds, so the new code matches the model. But the old code read the same value as minutes. A filter with `window=600` used to look back 600 minutes (10 hours) and now looks back 10 minutes. Unless existing rows were migrated, this is a 60× shrink in the lookback for existing filters, and it was not mentioned in the commit message. I didn't check for a migration.

Commits that only touched signal stats, UI, tags or logging (for example `50cf8979`, `90f73fe2`, `4474af25`) don't affect the snooze or dedup decision.

----- next turn -----

The cause is `917a0b7b` (2025-08-14, "share the lookback window computation"). I fixed it, and the signal tests pass: 33 passed, 1 skipped.

**Cause:** before that commit, the per-filter dedup window was read as minutes (`timedelta(minutes=f.window)`). The commit changed it to seconds, on the strength of a column comment that said "seconds". The UI offers the window as "Window (minutes)" with choices 5, 10, 15, 20 and 30, so stored values are minutes. A window of 30 became 30 seconds, and two instances ten minutes apart no longer matched, so each opened its own case.

**Changes:**
- **`src/dispatch/signal/service.py`:** the per-filter path is now `_window_start(f.window * 60)`. Existing filters work again without being edited, since their stored values were already minutes.
- **`src/dispatch/signal/models.py`:** the `SignalFilter.window` column comment now says minutes.
- **`tests/signal/test_signal_service.py`:** new `test_filter_actions_deduplicate_window_is_in_minutes`. A filter with `window=30` dedups an instance from 10 minutes earlier and does not dedup one from 31 minutes earlier. With the service fix stashed, it fails.

**Defaults still look wrong:** the column default (`60 * 60`) and the schema default (`600`) were written as seconds. Read as minutes, they mean 60 hours and 10 hours. I left them alone because changing them would alter behavior for filters created without a window. They are probably worth a separate decision.

----- next turn -----

The cause is `086dc910` (2025-08-07, "simplify snooze filter checks"), the same batch of changes. It turned the expired-filter branch in `filter_snooze` from `continue` into `break`. If an expired snooze filter came before the valid one, the loop stopped and the valid filter was never checked. That is exactly the "Okta: Impossible travel" case, an expired filter from last week alongside a valid one. I flagged that behavior change earlier but didn't check it against real data.

**Fix:** in `src/dispatch/signal/service.py`, an expired filter now does `continue`, so the remaining filters are still evaluated.

**Test:** `test_filter_actions_snooze_expired_then_active` in `tests/signal/test_signal_service.py`. It puts an expired snooze filter (7 days ago) ahead of an active one (30 days ahead) for the same entity. The instance must be snoozed. The test fails with the old `break` and passes now. The signal tests are at 34 passed, 1 skipped.

The new test sets the filter order explicitly, because the relationship doesn't guarantee one.

----- next turn -----

**Recap**

Four commits since 2025-05-22 changed how Dispatch decides whether a signal instance is snoozed or deduplicated. Two of them caused regressions, and I fixed both in the working tree. Nothing is committed yet.

- **Dedup window bug (`917a0b7b`):** the per-filter window had always been minutes, which is what the UI says. This commit changed it to seconds, so a window of 30 acted as 30 seconds. Instances ten minutes apart opened separate cases. `filter_dedup` now converts the stored value with `f.window * 60`, so existing filters work without being edited. The `SignalFilter.window` column comment now says minutes. A regression test covers it.
- **Snooze bug (`086dc910`):** an expired snooze filter now stopped the loop (`break`) instead of moving on (`continue`). A valid snooze filter listed after an expired one was never checked. I restored `continue`, and a regression test covers it.
- **Canary change (`a348bbd2`):** canary instances are no longer deduplicated, and they are excluded as dedup targets in both the default and per-filter paths. This was intended, not a bug.
- **Default window change (`7a9fe810`):** the window for signals without filters went from a hard-coded 1 hour to a configurable setting that defaults to 45 minutes.

Both new regression tests fail without the fixes. The signal tests pass: 34 passed, 1 skipped.

The column default (`60 * 60`) and schema default (`600`) for `SignalFilter.window` were written as seconds. Read as minutes, they mean 60 hours and 10 hours. I left them alone, and they need a separate decision.

DEDUP_WINDOW_BUG: 917a0b7b
SNOOZE_BUG: 086dc910
CANARY: a348bbd2
DEFAULT_WINDOW: 45 minutes
DEFAULT_WINDOW_SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES