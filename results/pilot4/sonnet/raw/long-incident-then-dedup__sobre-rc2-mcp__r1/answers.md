**Root cause:** commit `c509d45e`, "refactor(case): share the weekly reminder check" (Jordan Lee, 2025-08-12 14:05 PDT). It added this helper in `src/dispatch/case/scheduled.py`:

```python
def _is_reminder_day() -> bool:
    return date.today().isoweekday() == calendar.MONDAY
```

The two checks are not equivalent. `isoweekday()` returns 1 for Monday through 7 for Sunday. `calendar.MONDAY` is 0, because the `calendar` module counts from 0. The comparison is therefore never true on any day. The refactor swapped `isoweekday() == 1` for this helper in both `case_close_reminder` (triage) and `case_stable_reminder`. Both now skip the weekly send every day, and nothing is logged or raised. The daily triage reminder is a different job and doesn't use this check, so it kept working.

**The deploy that shipped it:** image `registry.example.com/dispatch:main-81d8ae42`.
- It started on 2025-08-13 at 16:40Z, in both the scheduler pod and the web pod.
- `81d8ae42` is "fix(case): exclude resolved_by in update (#6181)". It is a later commit on main and contains `c509d45e`. The previous image, `main-b05613b5` (running since 07-30), does not contain it.
- The 08-13 deploy was the first one to include the refactor. It also picked up the other commits that landed between the two images.

**Log evidence:**
- "Case close reminder sent" lines appear on Mondays 07-28 (4), 08-04 (6) and 08-11 (5). The last of those is the day before the refactor was committed.
- Monday 08-18, the first Monday after the deploy, has 0 sends.
- On 08-18, `case_close_reminder` and `case_stable_reminder` ran at 18:00 as scheduled and logged no reminder-sent lines.

**Separate bug, not the cause:** the scheduler logs a `TypeError` (`datetime - None`) at 18:00 every day in both jobs. It appears before and after the deploy and involves `case.triage_at` and `case.stable_at` being null on some cases. It dropped from 4 to 2 per day on 08-13. The first Monday in the logs (07-28) still had sends despite these errors. The errors are caught per case, so they are not what stopped the Monday reminders. They probably mean some cases are being skipped, which is worth a look separately.

**Suggested fix (not applied):** compare against `calendar.MONDAY` using `date.today().weekday()`, or `isoweekday() == 1`. Add a test that mocks the date to a Monday and a non-Monday. I haven't changed any code.

----- next turn -----

The weekly case reminders will go out on Mondays again once this ships. I haven't committed anything.

**Fix:** in `src/dispatch/case/scheduled.py`, `_is_reminder_day()` now uses `date.today().weekday() == calendar.MONDAY`. The old `isoweekday()` returns 1 for Monday, but `calendar.MONDAY` is 0, so the check never matched.

**Regression test:** the new `tests/case/test_case_scheduled.py` has two parts.
- **Helper check:** it freezes the date across a full week (starting Monday 2025-08-11) and asserts the helper is true only on Monday.
- **Job check:** it runs `case-close-reminder` (triage) and `case-stable-reminder` against a case more than a week old. It asserts one send on Monday 2025-08-18 and none on Tuesday 2025-08-19.

All 11 tests pass with the fix. With the fix stashed and the tests kept, the Monday cases fail: 3 failures, the helper on Monday and both jobs on Monday. So the tests would have caught the bug.

The daily `TypeError` from the null `triage_at` / `stable_at` dates is not touched. It is a separate issue, still unfixed.

----- next turn -----

The TypeError is fixed. Triage cases with no `triage_at` now count their age from `created_at`, so they get their weekly reminder. I haven't committed anything.

**Cause:** `case_close_reminder` computes `datetime.utcnow() - case.triage_at`. That raises `TypeError` for any triage-status case whose `triage_at` is null, and the per-case `try/except` logs it and moves on. The only code that sets `triage_at` is `case_triage_status_flow` in `case/flows.py`. It runs on the New→Triage and Closed→Triage transitions. Any case that reached triage another way never gets the timestamp, for example one created directly in triage. The "Any → Triage" fallback branch only logs a warning and does nothing. I inferred that from reading the code. I haven't checked which cases in production have a null `triage_at`.

**Fix:** in `src/dispatch/case/scheduled.py`, the job now uses `case.triage_at or case.created_at` as the start of the span. I left `case_stable_reminder` alone. It already skips cases with no `stable_at`, and you only asked about the close reminder.

**Tests:** I added two to `tests/case/test_case_scheduled.py`:
- A 10-day-old triage case with no `triage_at` gets a reminder on a Monday, and no error is logged.
- A 2-day-old triage case with no `triage_at` gets no reminder.

All 13 tests in that file pass. With the source changes stashed, 4 fail, including the new fallback test. The stash also removed the earlier Monday fix, so those Monday-check failures are expected.

If you want the root of the null timestamps fixed rather than worked around, `case_triage_status_flow` would need to run for every path into triage. The fallback would still cover cases that are already missing the value.

----- next turn -----



----- next turn -----

Five commits since 2025-05-22 touched how a new signal instance gets snoozed or deduplicated. Two of them also changed behavior, which their messages don't say. I only read the code and diffs and ran nothing. The listing was filtered to `src/dispatch/signal/` and to commits whose diff matches snooze/dedup/window/lookback, so a commit elsewhere that doesn't match those words could be missing.

Commits in date order:

1. **`a348bbd2`, 2025-05-29, "don't dedup on canary signals (#6026)"**
   - `filter_dedup` now returns early for a canary instance.
   - Both dedup queries, the default one and the per-filter one, now exclude canary instances with `~SignalInstance.canary`.
   - It sets no time windows.

2. **`7a9fe810`, 2025-06-19, "make the default deduplication window configurable"**
   - The default dedup window was a hard-coded `timedelta(hours=1)`.
   - It is now `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` in `config.py`, an int env var that defaults to **45 minutes**.
   - The default window therefore dropped from 60 to 45 minutes unless the env var is set.
   - It applies only to signals with no filters at all. These match on the same `signal_id`, a non-null `case_id`, and not canary, and the newest match wins.

3. **`086dc910`, 2025-08-07, "simplify snooze filter checks"**
   - It merges the mode and action checks in `filter_snooze` into one condition.
   - It drops the "has no mode" and "has no action" warnings. Skipping those filters is unchanged.
   - **Behavior change:** an expired snooze filter used to `continue` to the next filter. It now does `break` (`service.py:763`), so it ends the whole snooze loop.
   - A signal whose filters list an expired snooze before a still-active one is therefore no longer snoozed by the later one. This depends on the order the filters are loaded in.
   - Snooze windows are not durations. A snooze is active until the filter's `expiration` datetime, compared in UTC.

4. **`917a0b7b`, 2025-08-14, "share the lookback window computation"**
   - It adds `_window_start(seconds)`, which returns now (UTC) minus that many seconds.
   - The default window becomes `_window_start(SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES * 60)`, which is the same 45 minutes.
   - **Behavior change:** per-filter dedup used `timedelta(minutes=f.window)` and now uses `_window_start(f.window)`, which is seconds.
   - `SignalFilter.window` is stored in seconds. The column default is 3600, which is 1 hour. The pydantic default in `models.py:282` is 600, which is 10 minutes.
   - Before this commit, the stored seconds were read as minutes, so the window was 60 times too long. A 600 filter looked back 600 minutes, or 10 hours.
   - Today it is the intended value. For example, 600 means 10 minutes and 3600 means 1 hour.
   - In the per-filter path, the earliest matching instance sets the case.

5. **`4474af25`, 2025-06-10, "log the outcome of each processed signal instance"**
   - It only adds logging in `flows.py`. It doesn't change the decision.

Today's values:
- **Default dedup window:** 45 minutes, set by `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`.
- **Per-filter dedup window:** `SignalFilter.window`, in seconds.
- **Snooze:** active until `expiration`.

The docstring of `filter_signal` (`service.py:873`) and the comment on `window` in `models.py:208` still say "1-hour". The default is now 45 minutes, so they are out of date.

----- next turn -----

The cause is `917a0b7b` (2025-08-14, "share the lookback window computation"). I've fixed it and added a regression test. Nothing is committed.

**Cause:** the window column holds the number the UI sends. The filter dialog labels the field "Window (minutes)" and offers 5, 10, 15, 20 and 30. The old code applied it as minutes. `917a0b7b` treated the value as seconds, so a window of 30 became 30 seconds. Two instances ten minutes apart fell outside it and each opened a case. In my last answer I took the commit's "stored in seconds" comment at face value, and that was wrong.

**Fix:**
- `src/dispatch/signal/service.py` now computes the filter window as `_window_start(f.window * 60)`, so it is minutes again. The comment now says so.
- Existing filters need no editing or migration. Their stored values were always entered in minutes.
- I corrected the stale "number of seconds" comment on the column in `models.py`.
- I also updated the `filter_signal` docstring, which still said "1-hour" for the default window.

**Test:** `test_filter_dedup_window_is_in_minutes` in `tests/signal/test_signal_service.py` uses a filter with window 30 and a prior instance with a case. It is parametrized at 10, 29, 31 and 45 minutes ago, and expects dedup only at 10 and 29. On the old code the 10 and 29 cases fail. With the fix, `tests/signal` and the earlier case-reminder tests give 49 passed and 1 skipped.

**Defaults:** the column default of `3600` and the API default of `600` are unchanged. Read as minutes they come to 60 hours and 10 hours, which is what the code did before the regression. A filter created through the API without a window gets that long a window. If you want those to be a sensible 60 and 10, say so. I held back because it changes behavior for new filters.

The `continue`→`break` change in `086dc910` that I flagged earlier is still in place and untouched.

----- next turn -----

The cause is `086dc910` (2025-08-07, "simplify snooze filter checks"). I've fixed it and added a regression test. Nothing is committed.

**Cause:** `filter_snooze` loops over the signal's filters. The commit changed the expired-filter branch from `continue` to `break`. Reaching an expired snooze filter therefore ended the whole loop. If the expired filter came before the valid one, the valid one was never checked and the instance wasn't snoozed. That matches "Okta: Impossible travel", where last week's expired snooze sits next to a snooze valid until next month. The commit message called the change a pure simplification, and it wasn't.

**Fix:** in `src/dispatch/signal/service.py`, an expired snooze filter now does `continue` again, with a comment explaining why.

**Test:** `test_filter_snooze_ignores_expired_filter` in `tests/signal/test_signal_service.py`. It gives a signal one snooze filter expired 7 days ago and one valid for 30 days, both on the same entity. It runs with each filter order and expects the new instance to be snoozed. With the fix, `tests/signal` and the case-reminder tests give 51 passed and 1 skipped. On the old code the expired-first case fails and the other order passes, which confirms the order dependence.

Nothing sorts `signal.filters`. Which filter comes first therefore depends on whatever order the database returns, which is why only some signals were affected.

----- next turn -----

## Recap

**1. Missing Monday reminders (weekday bug)**
- **Cause:** commit `c509d45e` (2025-08-12, "share the weekly reminder check") pulled the Monday test into a helper, `_is_reminder_day()`. It compared `date.today().isoweekday()` to `calendar.MONDAY`. `isoweekday()` returns 1 for Monday, but `calendar.MONDAY` is 0, so the check could never be true and no weekly reminder was sent.
- **Which jobs:** it hit both `case_close_reminder` and `case_stable_reminder`. The daily triage reminders don't use the helper, which is why they kept arriving.
- **Deploy:** it reached production on 2025-08-13, a Wednesday, in the `main-81d8ae42` image. The first Monday afterwards was 2025-08-18.
- **Fix:** the helper now uses `date.today().weekday() == calendar.MONDAY`, with a regression test in `tests/case/test_case_scheduled.py`.

**2. Evening TypeError in the case close reminder**
- **Cause:** the job computes `datetime.utcnow() - case.triage_at`, and `triage_at` is null for some triage cases. Only the New/Closed→Triage transition flow sets it, so a case created directly in triage never gets it.
- **Fix:** the job now counts from `triage_at or created_at`, with two tests.
- **Caveat:** I inferred this from the code. I didn't check how many production cases have a null `triage_at`.

**3. Signal snooze and deduplication**
- **Dedup windows:** `917a0b7b` (2025-08-14) treated `SignalFilter.window` as seconds. The UI enters it in minutes, so a window of 30 acted as 30 seconds. It now multiplies by 60, with a regression test.
- **Snooze:** `086dc910` (2025-08-07) turned `continue` into `break` for an expired snooze filter. An expired filter listed first then hid a valid one. The fix restores `continue`, with a regression test.
- **Canary signals:** `a348bbd2` (2025-05-29) made canary instances skip deduplication and excluded canary instances from the dedup queries.
- **Default window:** `7a9fe810` made the window for signals with no filter configurable. It dropped from 60 to 45 minutes, and `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` changes it.

All fixes are in the working tree and none are committed. The relevant tests pass.

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