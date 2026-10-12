**Root cause:** commit `c509d45e` ("refactor(case): share the weekly reminder check", Jordan Lee, 2025-08-12) broke the Monday check. It replaced the inline `date.today().isoweekday() == 1` in `src/dispatch/case/scheduled.py` with a new helper:

```python
def _is_reminder_day() -> bool:
    return date.today().isoweekday() == calendar.MONDAY
```

`calendar.MONDAY` is `0`, but `isoweekday()` numbers Monday as `1`. The helper therefore never returns true (`isoweekday()` is never 0). Both `case_close_reminder` (long-running triage cases) and `case_stable_reminder` (stable cases) use it, so neither sends its weekly reminder any more. The daily `case_triage_reminder` doesn't use the helper, which is why it still arrives. The fix is to compare with `1`, or use `date.today().weekday() == calendar.MONDAY`. I haven't changed any code.

**Evidence from the logs:**
- "Case close reminder sent" appears on the Mondays 07-28 (4), 08-04 (6) and 08-11 (5), and never again.
- On Monday 08-18 the 18:00 run completed with no close reminders. Daily triage reminders and the incident close reminder still went out that day.
- The traceback line numbers in `scheduler.py` also shift between 08-11 and 08-14 (`case_close_reminder` line 43 → 47), which matches the new helper being added.

**Deploy that shipped it:** image `registry.example.com/dispatch:main-81d8ae42`, started on both the API and the scheduler on 2025-08-13 at about 16:40Z. It was the first production deploy after the previous image, `main-b05613b5` (2025-07-30), and contains the 28 commits in `b05613b5..81d8ae42`.

- `c509d45e` is an ancestor of `81d8ae42` and is not in `b05613b5`.
- Monday 08-11 was still served by the old image, so the Monday reminders last worked then. 08-18 is the first Monday on the new image and the first missed one.

**Unrelated noise:**
- Both reminder jobs log a `TypeError` (`datetime - None`) for some cases that have no `triage_at` or `stable_at`. `32fa810f` guards `stable_at` in the source, but the logs still show the error through 08-20. This has been happening since before the regression and doesn't explain the missing reminders.
- There was a database outage on 2025-08-15 at about 14:40Z. It affected other scheduled jobs, not the Monday reminders.

----- next turn -----

Fixed. Neither change is committed yet.

**Fix:** in `src/dispatch/case/scheduled.py`, `_is_reminder_day()` now uses `date.today().weekday() == calendar.MONDAY`. `weekday()` numbers Monday as 0, which is what `calendar.MONDAY` expects. The old `isoweekday()` numbers Monday as 1, so the check never matched.

**Tests:** the new file `tests/case/test_case_scheduled.py` has 7 tests, and all pass with the fix.
- `_is_reminder_day` is true on a Monday and false on a Tuesday and a Sunday.
- The registered `case-close-reminder` (triage) and `case-stable-reminder` jobs each send for a 10-day-old case on a Monday and don't on a Tuesday. These tests fake `date` so the weekday is fixed.

With the fix stashed, the three Monday cases fail, so the tests would have caught the regression. I only ran the new test file, not the full suite.

I did not touch the separate `datetime - None` errors in the logs for cases with no `triage_at`. `case_close_reminder` still subtracts `case.triage_at` without a `None` check, so those errors will keep appearing in the logs.

----- next turn -----

Fixed. The close reminder job no longer throws, and cases with no triage timestamp now get their weekly reminder. The change is uncommitted.

**Cause:** `case_close_reminder` computes `datetime.utcnow() - case.triage_at`. `triage_at` is only set in `case_triage_status_flow` (`src/dispatch/case/flows.py:592`), which runs on a status transition into triage. Cases in triage that never went through that flow have `triage_at = NULL`. The subtraction then raises `TypeError`, which the per-case `try/except` logs. That is why it appears every evening, and those cases were never eligible for the weekly reminder, even before the Monday-check regression. I inferred the "never went through the flow" part from the code. I haven't checked the production data to see how those cases were created.

**Fix:** in `src/dispatch/case/scheduled.py`, the job now counts from `case.triage_at or case.created_at`.

**Tests:** I added a test to `tests/case/test_case_scheduled.py`. A 10-day-old case with no `triage_at` gets a reminder on a Monday and not on a Tuesday. A 2-day-old one never does. The test also checks that nothing is logged as an exception. All 9 tests in the file pass. With the source change stashed, the new tests fail along with the earlier Monday ones. I only ran this test file, not the full suite.

**Not changed:** `case_stable_reminder` still skips stable cases with no `stable_at` (the guard from `32fa810f`), so those cases never get the weekly reminder. You only asked about the close reminder, so I left it. If you want them to count from creation too, it's the same one-line change.

----- next turn -----



----- next turn -----

Five commits touched the snooze/dedup logic since 2025-05-22. Four changed what Dispatch decides, and one only added logging. Three of the four were described as refactors or config changes, but they changed behaviour. All the code is in `src/dispatch/signal/service.py`, except the config entry below. I only read the code and diffs, and didn't run anything.

**Commits that changed the decision**

1. **`a348bbd2` (2025-05-29), "don't dedup on canary signals (#6026)"**
   - `filter_dedup` now returns immediately for a canary instance, so canaries are never deduplicated.
   - Canary instances are also excluded when looking for an earlier instance to dedup against, in both the default branch and the per-filter branch.
   - It doesn't touch any time window.

2. **`7a9fe810` (2025-06-19), "make the default deduplication window configurable"**
   - This is the window for signals that have no filters at all. It was a hard-coded `timedelta(hours=1)`. It is now read from `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` in `config.py`.
   - The default is **45 minutes**, so the default window shrank from 60 to 45 minutes even though the message reads as a pure config change.
   - Today the code applies `_window_start(SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES * 60)`, which is 2700 seconds (45 minutes) unless the env var overrides it.

3. **`086dc910` (2025-08-07), "simplify snooze filter checks"**
   - It collapsed the mode and action checks in `filter_snooze` into one condition and dropped the "no mode" and "no action" warnings. That part is equivalent in effect.
   - It also changed `continue` to `break` when a snooze filter's `expiration` is already past.
   - Today, the first expired active snooze filter stops evaluation of every later filter on that signal. Before, later unexpired snooze filters were still checked, so a signal can now be wrongly un-snoozed.
   - This is an expiration timestamp, not a window. Snooze has no lookback window.

4. **`917a0b7b` (2025-08-14), "share the lookback window computation"**
   - It added `_window_start(seconds)`.
   - The per-filter dedup window changed from `timedelta(minutes=f.window)` to `timedelta(seconds=f.window)`.
   - The column is documented in seconds (`SignalFilter.window`, default `60*60`, so 3600). The pydantic default is 600, which is 10 minutes.
   - Before, a stored `3600` meant 3600 minutes (60 hours). Now it means 1 hour, and the pydantic default of 600 means 10 minutes rather than 600 minutes (10 hours).
   - This probably fixes a unit bug, but it silently shrinks the effective window of every existing dedup filter by 60×. I'd check with the author whether that was intended.

**Not a decision change:** `4474af25` (2025-06-10) only adds `log.info` lines in `signal/flows.py` about each instance's outcome.

I left out commits that only touch signals in other ways, such as `d2675cf4`, which masks sensitive fields, and `5e136d7b`, which adds UI views.

----- next turn -----

**Which commit:** `917a0b7b` (2025-08-14, "share the lookback window computation"). It changed the per-filter lookback from `timedelta(minutes=f.window)` to `timedelta(seconds=f.window)`, on the theory that the column was in seconds. The UI (`SignalFilterCreateDialog.vue`, label "Window (minutes)", choices 5/10/15/20/30) and the stored values are in minutes. Your filter's `30` therefore became a 30-second window, so two instances ten minutes apart no longer matched.

**Fix:**
- `src/dispatch/signal/service.py`: `_window_start` now takes minutes and uses `timedelta(minutes=...)`. Per-filter windows use `f.window` as minutes again, and the default window passes `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` directly (still 45 minutes). Existing filters work without editing, because their stored values were always minutes.
- `src/dispatch/signal/models.py`: the column comment said "seconds … 1 hour". I corrected it to minutes.

**Test:** I added `test_filter_actions_deduplicate_window_is_in_minutes` in `tests/signal/test_signal_service.py`. It uses a filter with `window=30` and an earlier instance 10 minutes old, and expects the new instance to be deduplicated. It fails with the old code and passes now. The signal service tests give 15 passed and 1 skipped, and I haven't run the full suite. Nothing is committed.

**For you to decide, not changed:**
- **Column default:** the column default is still `60*60` and the pydantic default is `600`. In minutes those are 60 hours and 10 hours. They only apply to filters created without a window, and the old comment suggests 3600 was meant as seconds. I left them alone.
- **Snooze `break`:** the snooze `continue`→`break` change from `086dc910` is a separate behaviour change and is still in place.
- **Cases already split:** cases already opened as duplicates since 2025-08-14 aren't merged by this fix.

----- next turn -----

**Cause:** `086dc910` ("simplify snooze filter checks", 2025-08-07). It changed `continue` to `break` for the case where a snooze filter's `expiration` is already past. In `filter_snooze`, the first expired snooze filter now ends the loop, so later filters never run. For "Okta: Impossible travel", the filter that expired last week is checked first, the loop stops, and the one valid until next month is never looked at. I flagged this change in my first answer, but I hadn't tied it to a report until now.

**Fix:** in `src/dispatch/signal/service.py`, an expired filter is skipped with `continue` again, so evaluation goes on to the remaining filters.

**Test:** I added `test_filter_snooze_skips_expired_filter_and_applies_later_valid_one` in `tests/signal/test_signal_service.py`. It gives a signal two snooze filters on the same entity, one expired 7 days ago and one valid for 30 more days, and expects the new instance to be snoozed. With the `service.py` changes stashed, it fails along with the earlier window test. With the fix, all of `tests/signal` passes: 34 passed, 1 skipped. I haven't run the full suite. Nothing is committed.

**Caveat:** the test depends on the expired filter being evaluated first. It does fail without the fix, but the relationship has no explicit ordering. In production the order is also whatever the database returns, which is consistent with what you saw.

----- next turn -----

## Recap

**Investigation 1: weekly Monday reminders stopped**
- `_is_reminder_day()` in `src/dispatch/case/scheduled.py` compared `date.today().isoweekday()` (Monday is 1) with `calendar.MONDAY` (which is 0). The check never passed, so the weekly close reminders for long-running triage and stable cases were never sent. The daily triage reminders don't use that check, which is why they kept arriving.
- Commit `c509d45e` (2025-08-12, "share the weekly reminder check") introduced it. It shipped in image `main-81d8ae42`, which the logs show starting on 2025-08-13 at 16:40Z. The previous image was `main-b05613b5`.
- The last Monday before that deploy was 2025-08-11, so the first Monday that missed its reminders was 2025-08-18.
- The fix compares `date.today().weekday()` with `calendar.MONDAY`. The regression tests are in `tests/case/test_case_scheduled.py`.

**Investigation 2: the evening `TypeError` in the case close reminder**
- `case_close_reminder` computed `datetime.utcnow() - case.triage_at`. Triage cases whose `triage_at` is NULL raised a `TypeError` every evening, and they never got their weekly reminder.
- The job now counts from `case.triage_at or case.created_at`, with a test.
- I haven't checked the production data to confirm how those cases ended up without `triage_at`. That part is inferred from the code. `case_stable_reminder` still skips stable cases with no `stable_at`. I left it unchanged.

**Investigation 3: signal deduplication and snoozing**
- Commit `917a0b7b` read the per-filter dedup window as seconds when it is stored and entered in minutes, so a window of 30 became 30 seconds. I fixed it and added a test.
- Commit `086dc910` changed `continue` to `break` on an expired snooze filter. One expired filter then stopped later valid snooze filters from running. I fixed it and added a test.
- Commit `a348bbd2` changed canary handling: canaries are not deduplicated and are ignored when looking for an instance to dedup against.
- Commit `7a9fe810` made the default dedup window for signals without filters configurable. It was 1 hour and the default is now 45 minutes.
- All of this is uncommitted. I only ran the signal and case reminder tests, not the full suite.

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