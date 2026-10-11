Four commits since 2025-05-22 changed how Dispatch decides whether a new signal instance is snoozed or deduplicated. I haven't changed any code. All four touch `src/dispatch/signal/service.py` (`filter_snooze` and `filter_dedup`), and one also touches `src/dispatch/config.py`.

1. **`a348bbd2` (2025-05-29), "don't dedup on canary signals" (#6026).**
   - `filter_dedup` now returns immediately if the incoming instance is a canary.
   - Canary instances are also excluded from the lookback queries, both the default one and the per-filter one.
   - The time windows are unchanged.

2. **`7a9fe810` (2025-06-19), "make the default deduplication window configurable".**
   - This applies when the signal has no filters at all. The hard-coded `timedelta(hours=1)` became `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`, added to `config.py`.
   - It is read from the environment variable of the same name, cast to int, with a default of **45 minutes**.
   - The default therefore dropped from 60 to 45 minutes, which is a behavior change.

3. **`086dc910` (2025-08-07), "simplify snooze filter checks".**
   - It was labelled a refactor, but it changes behavior. The separate "no mode" and "no action" warnings and skips were folded into one condition: skip any filter that isn't active or isn't a snooze.
   - Snooze expiry is still compared in UTC, but an expired snooze filter now ends the loop with `break` instead of skipping to the next filter. Filters listed after an expired snooze filter are no longer checked.
   - A snooze filter with no expiration is still skipped with a warning.
   - Snooze has no lookback window, only the filter's `expiration` datetime.

4. **`917a0b7b` (2025-08-14), "share the lookback window computation".**
   - It added `_window_start(seconds)`, which returns now (UTC) minus that many seconds, and both dedup paths use it.
   - The default path calls `_window_start(SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES * 60)`, so it is still 45 minutes (2700 s). This part changes nothing.
   - The per-filter path changed from `timedelta(minutes=f.window)` to `f.window` in **seconds**. The model comment and column describe `window` as seconds, with a default of `60*60`, which is 1 hour. The pydantic schema default is `600`, which is 10 minutes.
   - The old code treated that number as minutes. For example, a stored value of 3600 meant 3600 minutes (60 hours) before and is now 1 hour. That makes this a real behavior fix despite the "refactor" label.

**Windows as the code applies them today:**

| Case | Window | Unit |
|---|---|---|
| No filters on the signal | 45 by default, configurable via `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` | minutes (converted to 2700 s) |
| Dedup filter | `SignalFilter.window`, with a DB default of 3600 and a schema default of 600 | seconds |
| Snooze filter | none; it runs until `expiration` | UTC datetime |

The 3600 DB default and 600 schema default come from the model and schema as they stand, not from these commits. Some commits that look related, such as `4474af25` (logging outcomes) and `d2675cf4` (masking raw fields), don't change the snooze or dedup decision, so I left them out.

----- next turn -----

**Cause:** `917a0b7b` (2025-08-14, "share the lookback window computation"). It was labelled a refactor, but it changed `f.window` from `timedelta(minutes=f.window)` to `timedelta(seconds=...)`. The UI's filter dialog is labelled "Window (minutes)" and offers 5, 10, 15, 20 and 30, so stored values are minutes. After that commit, a window of 30 meant 30 seconds. Two instances ten minutes apart therefore fell outside the window and each opened its own case.

**Fix:**
- `src/dispatch/signal/service.py`: `_window_start` now takes minutes. The per-filter path uses `f.window` as minutes again, and the no-filter default passes `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` directly, still 45 minutes. Existing filters work without editing and no migration is needed, because the stored values were always minutes.
- `src/dispatch/signal/models.py`: the column comment said seconds and defaulted to 3600, which would now mean 60 hours. I changed it to 60 (minutes), the same 1 hour. I also changed the schema default from 600 to 60. That default change goes beyond your request, so say if you'd rather I revert it.

**Test:** I added `test_filter_actions_deduplicate_window_is_in_minutes` in `tests/signal/test_signal_service.py`. It uses a window of 30 and an earlier instance ten minutes old with a case. It expects the new instance to be deduplicated into that case.
- With the fix, `python -m pytest tests/signal` gives 33 passed and 1 skipped.
- With only the `src` changes stashed, the new test fails, so it does catch the bug.

I haven't committed anything.

----- next turn -----

**Cause:** `086dc910` (2025-08-07, "simplify snooze filter checks"). It was labelled a refactor, but it changed the expired-filter branch in `filter_snooze` from `continue` to `break`. As soon as the loop reached an expired snooze filter, it stopped. A valid snooze filter listed after it was never checked, so the "Okta: Impossible travel" instances weren't snoozed. This matches the note on that commit in my first answer.

**Fix:** In `src/dispatch/signal/service.py`, an expired snooze filter now does `continue`, so the loop goes on to the next filter. A filter that matches still ends the loop with `break`, as before.

**Test:** I added `test_filter_actions_snooze_expired_filter_does_not_mask_valid_filter` in `tests/signal/test_signal_service.py`.
- It gives the signal two snooze filters for the same entity, an expired one (7 days ago) listed first and a valid one (30 days ahead) second. It expects the instance to be snoozed.
- With the fix, `python -m pytest tests/signal` gives 34 passed and 1 skipped.
- With the `src` changes stashed, the new test fails.

Nothing is committed. The working tree now holds both fixes, the dedup window fix and this one.

----- next turn -----

Two commits since 2025-05-22 introduced regressions in signal filtering. I fixed both in the working tree and added a regression test for each. Nothing is committed.

- **Deduplication windows:** `917a0b7b` presented itself as a refactor but changed a filter's `window` from minutes to seconds. The UI offers windows of 5 to 30 minutes, so a window of 30 acted as 30 seconds. Instances ten minutes apart opened separate cases. `window` is minutes again, and existing filters work without edits or a migration. I also changed the stored and schema defaults to 60 minutes. Both previously assumed seconds, at 3600 and 600.
- **Snoozing:** `086dc910` presented itself as a refactor but changed an expired snooze filter from `continue` to `break`. An expired filter listed first stopped the loop, so a valid filter after it was never checked. It now skips the expired filter and keeps checking.
- **Canary signals:** `a348bbd2` stopped canary signals from being deduplicated. Canary instances are skipped by dedup and ignored when looking for earlier instances. I did not change this.
- **Default window:** `7a9fe810` made the default dedup window configurable. It replaced a fixed 1 hour with a 45-minute default for signals without filters, so the default quietly dropped by 15 minutes. I did not change this either.

`python -m pytest tests/signal` gives 34 passed and 1 skipped. Each new test fails without its fix.

DEDUP_WINDOW_BUG: 917a0b7b
SNOOZE_BUG: 086dc910
CANARY: a348bbd2
DEFAULT_WINDOW: 45 minutes
DEFAULT_WINDOW_SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES