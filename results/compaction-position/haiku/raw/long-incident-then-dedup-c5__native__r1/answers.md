**Root cause:** the weekly check compares against the wrong constant. `calendar.MONDAY` is `0` (Python's `weekday()` numbering, Monday = 0), but `date.today().isoweekday()` is 1-based (Monday = 1). So `_is_reminder_day()` returns False on every day, and the weekly close and stable reminders never fire. The daily triage reminder has no weekday check, so it keeps working.

**The change:** commit `c509d45e` ("refactor(case): share the weekly reminder check", Jordan Lee, 2025-08-12 14:05 PT). It moved the inline `date.today().isoweekday() == 1` into the new helper, which is at `src/dispatch/case/scheduled.py:31-33`:

```python
def _is_reminder_day() -> bool:
    return date.today().isoweekday() == calendar.MONDAY
```

The refactor looks behavior-preserving, but `1` became `calendar.MONDAY`, which is `0`. Both call sites now use the helper: `case_close_reminder` at line 49 and `case_stable_reminder` at line 95.

**The deploy:** the scheduler pod `scheduler-mhtsgqwwx-q5q2n` started at 2025-08-13T16:40:06Z on `registry.example.com/dispatch:main-81d8ae42` (`scheduler.log:18851`). The web pod restarted with the same image at the same time. Commit `c509d45e` is an ancestor of `81d8ae42`, so that image ships it. The scheduler was on `main-b05613b5` from Jul 30 until then.

**Evidence from the logs:**
- Monday 2025-07-28, 08-04 and 08-11 each sent close reminders (4, 6 and 5 sends). The 08-11 run was still on the old image.
- Monday 2025-08-18, the first Monday on the new image, sent none. The job ran (`case_close_reminder` elapsed line at `scheduler.log:25275`) and logged no error or warning. Daily triage reminders kept sending on 08-14 through 08-20.
- I confirmed in Python that `calendar.MONDAY == 0` and that `isoweekday()` for 2025-08-18 is 1, so the check is False.

**Caveats:**
- The logs end on 08-20, so 08-18 is the only affected Monday in the data.
- The stable reminder never sent anything in this window, so the logs cannot show whether it also worked before the deploy. The same helper change affects it, so I expect the same failure.
- The `TypeError: ... 'NoneType'` errors in the logs are a separate, pre-existing problem. `case_close_reminder` has no `triage_at is None` guard (`scheduled.py:43-47`), so one case fails per day. Commit `32fa810f` added a `stable_at` guard, but it did not cover the triage path. These errors are caught per case, so they did not cause the missing Monday sends.

**Suggested fix (not applied):** compare against `calendar.MONDAY` only after using `datetime.weekday()`, or go back to `isoweekday() == 1`. Add a test for `_is_reminder_day`, since no test covers that helper. I have not changed any code.

----- next turn -----

The weekly reminder check is fixed and there's a regression test for it. Nothing is committed.

**The fix** (`src/dispatch/case/scheduled.py:33`): `_is_reminder_day()` now uses `date.today().weekday() == calendar.MONDAY`. Both sides are 0-based, so Monday matches again. I kept `calendar.MONDAY` rather than hard-coding `1`.

**The regression test** (new file `tests/case/test_case_scheduled.py`): it pins `date.today()` to each day from Monday 2025-08-11 through Sunday 2025-08-17 and asserts that only Monday returns True. I used a monkeypatched `date` class because no time-freezing library is installed.

**Verification:**
- New test on the fixed code: 7 passed.
- New test with the broken `isoweekday()` check restored temporarily: the Monday case fails, the other six pass. That's the failure you'd have seen before the fix. The fix is back in place afterward.
- `python -m pytest tests/case`: 22 passed, including the new file. I didn't run the full suite.

**Not changed:**
- `src/dispatch/incident/scheduled.py:229` uses `isoweekday() == 1`, which is correct, so I left it.
- The `NoneType` errors from `case_close_reminder` when `triage_at` is None are still there. They're caught per case and don't block other sends, so I didn't touch them here.
- I didn't add a job-level test for `case_close_reminder`. The scheduled-task wrapper opens real per-organization sessions, so testing it would take more setup than this fix warrants.

----- next turn -----

The nightly `TypeError` is `case.triage_at` being `None` for a case in triage. The job now counts from `created_at` in that case, and there's a test for it. I couldn't tie the error to one specific case, because the log line has no case ID.

**What causes it:** a case can be in `triage` without `triage_at` being set. `triage_at` is only written by `case_triage_status_flow`, and some paths never call it:
- **Stable or escalated → triage through the status dispatcher** (`src/dispatch/case/flows.py:766`). The fallback branch logs a warning and sets no timestamp.
- **Slack "reopen" button** (`src/dispatch/plugins/dispatch_slack/case/interactive.py:1427`). It sets `case.status = CaseStatus.triage` directly, so no triage flow runs and no timestamp is set. A case that was created as closed, and never had `triage_at` set, keeps `None` when reopened.

The logs don't record which transition produced the bad case, so I can't say which path hit it. Both fit the nightly pattern of one failing case per day.

**The fix** (`src/dispatch/case/scheduled.py:47-50`): the job counts from `case.triage_at or case.created_at`. The case still gets its weekly reminder, and cases with a `triage_at` behave as before. I left the two paths above unchanged, since you asked for the fallback. The stable reminder still skips cases with no `stable_at`, as it did before.

**Tests** (`tests/case/test_case_scheduled.py`): the file now has three tests that call the real close-reminder body against the test database, with the send function mocked and Monday pinned.
- A triage case with no `triage_at`, created 8 days ago, gets a reminder.
- A triage case with no `triage_at`, created 3 days ago, does not.
- A case with a recent `triage_at` but an old `created_at` is counted from `triage_at`.

Without the fallback, only the first test fails, which is the expected result. Running `python -m pytest tests/case` gives 25 passed.

**Something I found along the way:** `CaseFactory` in `tests/factories.py` has `class Params: status = "New"`, so passing `status=` to it is silently ignored and every case is created as New. I didn't change the factory. The new tests set the status after creating the case, and a comment in the helper explains why.

Nothing is committed. The working tree has the Monday fix from last time, plus this change and the test file.

----- next turn -----

Two commits changed how a window is applied since 2025-05-22, and one of them changes the unit for existing filters. I didn't change any code.

**Commits that changed snooze/dedup behavior** (`src/dispatch/signal/service.py` unless noted):

1. **`a348bbd2`** (2025-05-29), "fix(signal): don't dedup on canary signals". Canary instances are skipped by dedup and never match as duplicates. No window change.
2. **`7a9fe810`** (2025-06-19), "make the default deduplication window configurable". Signals with no dedup filter used a hard-coded 1 hour. They now use `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` (`src/dispatch/config.py:95`), which defaults to **45 minutes (2700 s)** and can be overridden by env var. The `filter_signal` docstring still says 1 hour.
3. **`086dc910`** (2025-08-07), "simplify snooze filter checks". Removed the "no mode" and "no action" warnings and merged the checks into one condition. The behavior change is that an expired snooze now does `break` instead of `continue`, so later snooze filters on the same signal are no longer evaluated. No window change.
4. **`917a0b7b`** (2025-08-14), "share the lookback window computation". This changes the unit for per-filter dedup windows. It was `timedelta(minutes=f.window)` and is now `_window_start(f.window)`, which treats `f.window` as **seconds**. The default-window path is unchanged in effect, still 45 minutes via `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES * 60`.

I also checked `4474af25` (logging only), `d2675cf4` (masks raw fields, no filter logic), and `5e136d7b` (a `model_rebuild()` call). None changes the decision.

**Current values as the code applies them:**
- **Snooze:** no window. A snooze filter applies while its `expiration` is in the future. With no `expiration` it is skipped with a warning. With no `expression` it snoozes every instance of the signal.
- **Default dedup** (signal has no dedup filters): lookback of **45 minutes** by default. It matches the most recent instance with a case and excludes canaries.
- **Per-filter dedup window:** `SignalFilter.window` is read as **seconds**. The column default is 3600 s (1 hour, `src/dispatch/signal/models.py:206-208`). The API schema default is 600 (`models.py:282`), which is 600 seconds (10 minutes) under the current code.
- **UI:** the create dialog offers 5, 10, 15, 20, 30 under a "Window (minutes)" label (`SignalFilterCreateDialog.vue:196`). It sends those values unchanged, so a "15 minute" filter now dedups over 15 seconds.

**Concern:** `917a0b7b` conflicts with how the UI and its label define the field. Before it, the backend treated the stored number as minutes, which matched the UI. The model comment and the stored unit say seconds. Unit-wise, `917a0b7b` silently shortens every UI-created dedup filter by 60×.

**Deployment:** `086dc910` is in image `main-81d8ae42`, which the logs show running from 2025-08-13. `917a0b7b` (2025-08-14) is not in that image. It is on `main` now, and I can't confirm from here whether it has been deployed since.

----- next turn -----

The cause is `917a0b7b` ("refactor(signal): share the lookback window computation", 2025-08-14). It changed the per-filter window from minutes to seconds. A filter set to 30 in the UI became a 30-second window, so instances ten minutes apart were never grouped. The fix is in place and the regression test passes. Nothing is committed.

**The fix** (`src/dispatch/signal/service.py`): `_window_start` takes minutes again, and the per-filter window passes `f.window` straight through, so 30 means 30 minutes. The default-window path passes `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` directly, so it still means 45 minutes.

**Existing filters** keep working without edits. The UI has only ever offered 5–30 under a "minutes" label and stores those values unchanged, so the stored numbers already mean minutes.

**Regression tests** (`tests/signal/test_signal_service.py`): a parametrized test with two instances for the same entity, created ten minutes apart.
- Window 30 → the second instance is deduplicated onto the first one's case. This is the reported case.
- Window 5 → not deduplicated, which guards against a fix that ignores the window.

With the seconds version restored, the window-30 test fails. With the fix, both pass. Running `python -m pytest tests/signal tests/case` gives 59 passed, 1 skipped.

**Things I left alone, which you should decide on:**
- The `SignalFilter.window` column default is still `60 * 60`, and the API schema default is still `600`. Both now mean minutes, so a filter created without a window gets 60 hours (column default) or 10 hours (schema default). The stale comment said these were seconds. I changed the comment to minutes but not the numbers, since changing them changes behavior for filters created without a window. Setting the column default to 60 would match the original "1 hour" intent.
- The `filter_signal` docstring still says the default dedup window is 1 hour. It has been 45 minutes (configurable) since `7a9fe810`.

----- next turn -----



----- next turn -----

The cause is commit `086dc910` ("refactor(signal): simplify snooze filter checks", 2025-08-07). In `filter_snooze` (`src/dispatch/signal/service.py`), an expired snooze filter hit `break`, which ended the loop over the signal's filters. Any valid snooze filter after the expired one was never checked. Once the first filter for the user expired, new instances for that user were no longer snoozed.

**Fix:** the expired check now uses `continue` instead of `break`, so the loop moves on to the next filter. Nothing about the existing filters changes.

**Regression test:** `test_filter_actions_snooze_skips_expired_filter` in `tests/signal/test_signal_service.py`. It creates an expired snooze filter followed by an active one, both matching the instance's entity, and asserts the instance is snoozed. It fails on the old code and passes with the fix.

**Results:** `python -m pytest tests/signal tests/case` gives 60 passed, 1 skipped.

Nothing is committed. The working tree now also includes the earlier changes to the Monday reminder, the dedup window, and the related tests.

----- next turn -----

## Recap

**Monday reminders (weekly case reminders not sent)**
- The weekday check in `src/dispatch/case/scheduled.py` compared `date.isoweekday()` (Monday = 1) with `calendar.MONDAY` (Monday = 0). It could never be true, so the weekly reminder never fired. It came in with `c509d45e` (2025-08-12) and shipped in `main-81d8ae42`, which started on 2025-08-13 at 16:40 UTC per the logs.
- The fix uses `date.today().weekday()`. A regression test covers each day of the week.
- The August 11 Monday ran before that deploy, so its reminders went out. The first missed Monday is August 18.

**Nightly TypeError (close reminder)**
- The close-reminder job subtracted `case.triage_at` from the current time. Cases that reached triage without a `triage_at` timestamp caused a TypeError, which is what the nightly logs show. The paths that can leave it unset are the dispatcher fallback in `flows.py` and the Slack reopen button. I could not tie the log errors to a specific case because they carry no case IDs.
- The job now counts from `triage_at`, falling back to `created_at`. Three tests cover the fallback, the too-recent case, and the case where `triage_at` takes precedence.

**Deduplication windows**
- `917a0b7b` (2025-08-14) changed the per-filter window from minutes to seconds. A window of 30 became 30 seconds, so instances ten minutes apart were never grouped. The fix restores minutes, and the regression test covers window 30 and window 5.
- Filters created in the UI already store minutes, so they work unchanged.

**Snoozing (valid snooze filter ignored)**
- `086dc910` (2025-08-07) changed the expired-filter check in `filter_snooze` to `break`. An expired snooze filter ended the loop, so a valid snooze filter later in the list was never checked. The fix is `continue`, with a regression test that fails on the old code.

**Canary signals**
- `a348bbd2` (2025-05-29, "don't dedup on canary signals") excludes canary instances from deduplication. Its filter test is still in place.

**Defaults**
- Signals without a filter are grouped with a 45-minute window, set by `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`, introduced in `7a9fe810`.

**Open items**
- Nothing is committed. The working tree holds all the fixes and tests.
- `SignalFilter.window` still has a column default of 3600 and a schema default of 600. Both now read as minutes, which is wrong for new filters that have no window set.
- The `filter_signal` docstring still says the default window is one hour.
- I could not confirm whether `917a0b7b` is in production. The logs end on 2025-08-20, and the dedup fix may not have deployed yet.

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