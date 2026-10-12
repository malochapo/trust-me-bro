**Root cause:** commit `c509d45e` ("refactor(case): share the weekly reminder check", Jordan Lee, 2025-08-12) broke the Monday check. It replaced `date.today().isoweekday() == 1` with a helper that compares against `calendar.MONDAY`:

```python
def _is_reminder_day() -> bool:
    return date.today().isoweekday() == calendar.MONDAY   # src/dispatch/case/scheduled.py:33
```

`isoweekday()` is 1-based (Monday = 1), but `calendar.MONDAY` is 0 (I checked this in Python: `calendar.MONDAY = 0`). So `_is_reminder_day()` is never true, and both `case_close_reminder` and `case_stable_reminder` skip every send. The triage reminder (`case_triage_reminder`) has no weekday gate, which is why daily triage reminders still arrive. The bug is still on `main`, and no later commit has touched that file.

**Why it's this deploy:**
- The logs show Monday close/stable sends on 2025-07-28 (4), 08-04 (6), and 08-11 (5). There are none on 08-18, the first Monday after the change.
- The scheduler and web pods restarted together at 2025-08-13 16:40 UTC (09:40 PDT). The scheduler pod changed from `xdp7k6gs2q` to `mhtsgqwwx` at that point.
- The traceback line numbers in `case_close_reminder` change on Aug 13 from 43/51 to 47/55, and the stable traceback lines are 93/101. Those match `c509d45e`'s file exactly, so the pods were running that version from Aug 13.
- The commit is the newest one touching `case/scheduled.py` before the restart. Commit `3d3bf623` (Aug 13, 11:47 PDT) is after the restart, so it's not in this deploy.

I couldn't find a deploy record in the repo or logs; the link between `c509d45e` and the Aug 13 restart comes from timing and line numbers.

**Things that look relevant but aren't:**
- The `TypeError` on `None` for `triage_at` and `stable_at` appears on every run from 07-28 onward. It's caught per case, so it doesn't stop the job. It's noise, not the cause of the Monday gap.
- The same deploy included `32fa810f` ("not all cases have a stable_at date"), which fixed the `stable_at` crash. That's why the stable traceback stops after Aug 12.

**Suggested fix (not applied):** use `date.today().weekday() == calendar.MONDAY` (0-based, matching `calendar`), or go back to `isoweekday() == 1`. Add a test that pins a known Monday. `incident/scheduled.py:229` still uses `isoweekday() == 1`, so it's unaffected.

----- next turn -----

The Monday reminder check is fixed, and there's a regression test that fails on the old code and passes on the new code. I haven't committed anything.

**The fix** (`src/dispatch/case/scheduled.py:33`): the helper now compares `date.today().weekday()` with `calendar.MONDAY`. Both are 0-based, so Monday matches. The old code compared the 1-based `isoweekday()` with `calendar.MONDAY` (0), which never matched.

**The regression test** (`tests/case/test_case_scheduled.py`, new file): it stubs `date.today()` for one full week (Aug 18–24, 2025) and checks that `_is_reminder_day()` is true only on Monday. I ran it against the unfixed code first: the Monday case failed (`1 failed, 6 passed`), so it catches this bug. After the fix, the full `tests/case/` directory passes (22 tests) using `python -m pytest`.

**Scope:** the test checks the helper, not the full job. The two reminder jobs call it, so they're covered by this change, but I didn't run an end-to-end send on a simulated Monday. I also didn't run the entire test suite, only `tests/case/`.

----- next turn -----

The close reminder now counts from `created_at` when `triage_at` is missing, and there are regression tests for it. All 25 tests in `tests/case/` pass with `python -m pytest`.

**Cause:** `triage_at` is only set by `case_triage_status_flow`. Some code paths set `case.status = CaseStatus.triage` without running that flow, so the case has no `triage_at`. The clearest one is the reopen button handler, `src/dispatch/plugins/dispatch_slack/case/interactive.py:1427`. The job then computes `datetime.utcnow() - None`, the `TypeError` is caught per case, and the case gets no reminder. The job's logs don't include case IDs, so I can't confirm which production cases are affected. I also haven't fixed the paths that skip the flow, so new cases can still end up without `triage_at`.

**Fix** (`src/dispatch/case/scheduled.py`, `case_close_reminder`): the job counts from `case.triage_at or case.created_at`. The span is computed the same way as before, so the Monday and week-based checks don't change.

**Tests** (`tests/case/test_case_scheduled.py`):
- No `triage_at`, created 8 days ago: reminded. This fails on the old code and passes now.
- No `triage_at`, created 2 days ago: not reminded.
- `triage_at` 2 days ago with `created_at` 30 days ago: not reminded. This makes sure `triage_at` still wins when it's set.

The tests call the job through `scheduler.registered_tasks`, because the decorator returns None. `CaseFactory` ignores `status=` as a keyword (it's declared under `class Params`), so the helper sets status on the case directly.

**Not changed:**
- `case_stable_reminder` still skips cases without `stable_at`, as it did before. You didn't ask me to change that, so tell me if stable cases should also count from `created_at`.
- The paths that set triage without the flow are still there, including `interactive.py:1427`.
- `created_at` is timezone-aware at creation but stored as a naive `DateTime`. The triage job already subtracts it from `utcnow()` the same way, so the new fallback follows that pattern. I haven't checked it against a real stored value.

----- next turn -----



----- next turn -----

Five commits since 2025-05-22 touch the snooze or dedup decision. Only two of them change a time window, and one of those changes its unit. I read the code and diffs but did not run anything, and I changed nothing.

**Current windows, as the code applies them**
- **Default dedup (filter without a deduplicate rule):** `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`, default 45 (`src/dispatch/config.py:95-96`). The code multiplies by 60 and treats the result as seconds, so the window is 45 minutes.
- **Per-filter dedup:** `SignalFilter.window`, read as **seconds** (`src/dispatch/signal/service.py:845-846`). The column default is 3600 (1 hour) in `models.py:206-208`, and the schema default is 600 (10 minutes) in `models.py:282`.
- **Snooze:** no lookback window. A snooze is active until `SignalFilter.expiration`, and the check is `expiration <= now`.

**Commits, oldest first**

1. **`a348bbd2`**, 2025-05-29, Will Sheldon, "fix(signal): don't dedup on canary signals (#6026)". `filter_dedup` returns early for canary instances. Canary instances are also excluded from the matches for both the default and the per-filter branches. No window change.

2. **`7a9fe810`**, 2025-06-19, Jordan Lee, "feat(signal): make the default deduplication window configurable". The default window was hard-coded to 1 hour and now reads `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`, which defaults to 45. This is a change of the default window from 60 minutes to 45 minutes, unless the env var is set.

3. **`086dc910`**, 2025-08-07, Sam Ortega, "refactor(signal): simplify snooze filter checks". Three changes in `filter_snooze`:
   - Filters with no mode or no action are now skipped silently. The warnings are gone.
   - An expired snooze used to `continue` to the next filter. It now `break`s out of the loop, so later active snooze filters are never checked. That is a behavior change, and the commit message calls it a refactor. Whether it matters depends on filter order, which I did not check.
   - No window change.

4. **`917a0b7b`**, 2025-08-14, Jordan Lee, "refactor(signal): share the lookback window computation". The per-filter branch was `timedelta(minutes=f.window)` before this commit. It is now `_window_start(f.window)`, which treats the value as seconds. So every per-filter dedup window became 60 times shorter. For example, a window of 600 went from 10 hours to 10 minutes. The default branch is unchanged in effect (45 minutes). The model comment has said "seconds" since 2022 (`ecbad47f`), so this change brought the code in line with the comment. Any filter saved with a minutes value now deduplicates over a much shorter period. I did not check the UI or the stored filter data to see which unit operators enter.

**Not in scope, but checked:** `4474af25` (2025-06-10) only adds log lines and doesn't change the decision. `d2675cf4` (2025-07-03, "mask sensitive raw fields before processing") touches `signal/flows.py` and `signal/redaction.py`, which feed the dedup expressions. I did not examine whether masking changes what those expressions match, so treat it as unverified.

----- next turn -----

The cause is `917a0b7b` (2025-08-14, Jordan Lee, "refactor(signal): share the lookback window computation"). Before that commit, a filter's window was read in minutes, as `timedelta(minutes=f.window)`. The commit changed it to seconds, so a window of 30 became 30 seconds. Your two instances, ten minutes apart, were never inside that window, so the second one opened a new case. The UI's "Window (minutes)" field, with options 5 to 30, is what the filter was meant to use.

**Fix** (`src/dispatch/signal/service.py`)
- `_window_start` takes minutes again, and the per-filter branch calls it with `f.window`. The default branch passes `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` directly.
- Stored filters are read the same way they were before the bad commit, so no filter needs editing.
- The comment on `SignalFilter.window` in `src/dispatch/signal/models.py` now says minutes.

**Regression test** (`tests/signal/test_signal_service.py`): `test_filter_actions_deduplicate_window_is_in_minutes`. It has a window of 30 and two instances on the same entity, the first created ten minutes earlier. It expects the second to be deduplicated. I checked that it fails when the window is read as seconds, and it passes with the fix.

**Test results:** `python -m pytest tests/signal tests/case` → 58 passed, 1 skipped.

**Not changed, needs a decision:**
- The `window` column default in `models.py` is still `60 * 60`. Under the minutes reading that is 60 hours, not 1 hour. The schema default of 600 was already read as minutes before the bad commit, so it is unchanged. Changing the column default needs a migration, and only matters for rows inserted without a window, so I left it.
- The snooze change in `086dc910` (`continue` became `break` on an expired snooze) still stands. It has nothing to do with this bug, but it can stop later active snooze filters from being checked.

Changes are uncommitted.

----- next turn -----

The cause is `086dc910` (2025-08-07, Sam Ortega, "refactor(signal): simplify snooze filter checks"). In `filter_snooze`, the expired-snooze check changed from `continue` to `break`. Once the loop reached an expired snooze filter, it stopped, so any later active snooze filter was never checked. For "Okta: Impossible travel", the expired filter came first, so new instances for that user were not snoozed.

**Fix** (`src/dispatch/signal/service.py`): restored `continue`, so an expired snooze is skipped and the loop goes on to the next filter.

**Regression test** (`tests/signal/test_signal_service.py`): `test_filter_actions_snooze_after_expired_snooze`. It has an expired snooze filter followed by an active one for the same entity, and expects the instance to be snoozed. It fails with `break` and passes with `continue`.

**Test results:** `python -m pytest tests/signal tests/case` → 59 passed, 1 skipped.

The `break` in `086dc910` was the only change to the snooze loop's control flow. I did not change its other edits (removing the warnings for filters with no mode or action) because they don't affect which instances get snoozed. The changes are uncommitted.

----- next turn -----

Both investigations are done. The changes are uncommitted in the working tree. Test results: `python -m pytest tests/signal tests/case` gives 59 passed, 1 skipped.

**Monday reminders (weekly case reminders missing)**
- The weekday check in `_is_reminder_day()` compared `date.today().isoweekday()` (Monday = 1) with `calendar.MONDAY` (Monday = 0), so it never matched. It went in with `c509d45e` (2025-08-12, "refactor(case): share the weekly reminder check"). The deploy that shipped it is image `main-81d8ae42`, started 2025-08-13 in `api.log`.
- Fix: compare with `date.today().weekday()`. Regression test: `test_is_reminder_day` in `tests/case/test_case_scheduled.py`. It fails on the old code and passes now.
- The api log only shows web containers. I didn't find the scheduler's own deploy record, so the image tag is the web deploy that contains `c509d45e`.

**Evening TypeError (case close reminder)**
- `case.triage_at` is NULL for some cases in triage. Some paths set triage without running the transition flow that stamps `triage_at`, most clearly the reopen button handler in `interactive.py`. The job then computes `datetime.utcnow() - None`, the error is caught per case, and the case gets no reminder.
- Fix: the job counts from `case.triage_at or case.created_at`. Three tests in `tests/case/test_case_scheduled.py` cover missing `triage_at`, a recent case, and `triage_at` winning over `created_at`.
- Not confirmed: which production cases lack `triage_at`, since the logs have no case IDs. The paths that skip the flow are still there.

**Deduplication window in minutes**
- `917a0b7b` (2025-08-14, "refactor(signal): share the lookback window computation") changed per-filter windows from minutes to seconds. A window of 30 became 30 seconds, so a 10-minute gap never grouped. The UI says "Window (minutes)".
- Fix: the window helper takes minutes again, so stored filters need no edits. Regression test: `test_filter_actions_deduplicate_window_is_in_minutes`.

**Snoozing after an expired snooze**
- `086dc910` (2025-08-07, "refactor(signal): simplify snooze filter checks") changed `continue` to `break` when a snooze filter had expired, so later active snooze filters were never checked.
- Fix: restored `continue`. Regression test: `test_filter_actions_snooze_after_expired_snooze`.

**Canary signals**
- `a348bbd2` (2025-05-29, "fix(signal): don't dedup on canary signals (#6026)") makes canary instances skip deduplication and excludes them from matches.

**Default window**
- Signals without a filter group instances over 45 minutes. The commit `7a9fe810` made this configurable; it was hard-coded at 1 hour before.

**Still open**
- The `window` column default in `models.py` is `60 * 60`, which under the minutes reading is 60 hours. It needs a migration to change, so I left it.
- The stable-case job still skips cases without `stable_at`. I didn't change it.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e
DEPLOYED_IMAGE: main-81d8ae42
FIRST_MISSED: 2025-08-18
MISSING_FIELD: triage_at
DEDUP_WINDOW_BUG: 917a0b7b
SNOOZE_BUG: 086dc910
CANARY: a348bbd2
DEFAULT_WINDOW: 45 minutes
DEFAULT_WINDOW_SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES