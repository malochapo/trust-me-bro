**Root cause:** commit `c509d45e` ("refactor(case): share the weekly reminder check", Jordan Lee, 2025-08-12) broke the Monday check in `src/dispatch/case/scheduled.py`.

The commit replaced `date.today().isoweekday() == 1` with a new helper, `_is_reminder_day()`. The helper compares `isoweekday()` to `calendar.MONDAY`. `isoweekday()` numbers Monday as 1, but `calendar.MONDAY` is 0 (I confirmed this by running it). So the check is never true, on any day.

Both `case_close_reminder` (triage cases) and `case_stable_reminder` (stable cases) use the helper. The `q >= 1 and _is_reminder_day()` branch is now dead code, so no weekly reminders go out and no error is logged. The daily triage reminders come from a separate code path, which is why they still arrive.

**The deploy that shipped it:** `registry.example.com/dispatch:main-81d8ae42`, rolled out on 2025-08-13 at about 16:40 UTC. The api pod and the scheduler pod both started that image then. `81d8ae42` is the commit right after `c509d45e` on main, so the image includes it. The earlier deploy, `main-b05613b5` on 2025-07-30, predates the commit.

**Log evidence:**
- Case close reminders were sent on 2025-07-28 (5), 08-04 (7) and 08-11 (6). All three dates are Mondays.
- On 2025-08-18, the first Monday after the deploy, no case close or stable reminder was sent. Only an incident close reminder went out, because the incident code path doesn't use the helper.

**Separate issue, not the cause:** from 2025-07-28 to about 08-11 the scheduler logged `TypeError: unsupported operand ... NoneType` in `case_stable_reminder` and `case_close_reminder`. `case.stable_at` (and apparently `triage_at`) was None for some cases. Commit `32fa810f` addressed the stable case on 08-11. This predates the outage and the Monday reminders still went out during it, so it didn't cause this.

**Suggested fix, once you want one:** make the helper compare `isoweekday() == 1`, or use `date.today().weekday() == calendar.MONDAY`. A small unit test of `_is_reminder_day()` with a frozen Monday date would have caught this. I haven't changed any code.

----- next turn -----

The weekly reminders should come back after this ships. The new test passes with the fix, and the two Monday cases fail without it. I ran only that new test file, not the full suite.

- **Fix:** in `src/dispatch/case/scheduled.py`, `_is_reminder_day()` now uses `date.today().weekday() == calendar.MONDAY`. Both sides are 0-based. Before, `isoweekday()` (Monday is 1) was compared to `calendar.MONDAY` (0), which never matched.
- **Regression test:** `tests/case/test_case_scheduled.py` patches `date.today()` and checks that two Mondays (2025-08-11 and 2025-08-18) return True. It checks that a Wednesday, a Friday and a Sunday return False.
- **Not committed:** I haven't committed anything, so nothing has deployed. Nothing changes in production until this is committed, merged and rolled out.

----- next turn -----

The nightly TypeError is fixed. Triage cases with no `triage_at` now get their weekly reminder, counted from when the case was created. The new tests pass, and the full suite wasn't run.

**Cause:** `case_close_reminder` computed `datetime.utcnow() - case.triage_at`, and `triage_at` is NULL for some cases in triage status. It is only set when a case goes through `case_triage_status_flow` (`src/dispatch/case/flows.py:594`), so cases that never went through that flow keep NULL. For those cases the job raised `TypeError`, the per-case `except` logged it, and the case was skipped. That is why it logged every evening and why those cases never got a reminder.

**Fix:** in `src/dispatch/case/scheduled.py`, the span is now `datetime.utcnow() - (case.triage_at or case.created_at)`.

**Tests:** I added four cases to `tests/case/test_case_scheduled.py` that run the real job with the case lookup and reminder sender stubbed out. They check that:
- a missing `triage_at` falls back to `created_at` and sends the reminder when the case is over a week old;
- a case created less than a week ago gets no reminder;
- `triage_at` takes precedence over `created_at` when both are set;
- a case with a `triage_at` but no `created_at` still gets its reminder.

With the source changes reverted, the fallback test fails. The Monday-check tests from before fail in that run too, since both fixes are in the same file.

**Stable job:** `case_stable_reminder` already skips cases with no `stable_at`, which is what `32fa810f` added. I left it alone because you only asked about the close reminder job. Those cases are silently skipped rather than falling back to `created_at`. I can make it behave the same way if you want.

Nothing is committed yet.

----- next turn -----



----- next turn -----

I've been reading the signal service's git history and the current code. I now have what I need.

Four commits since 2025-05-22 changed the snooze or dedup decision. All four touch `src/dispatch/signal/service.py`.

| Hash | Date | What it changed |
|---|---|---|
| `a348bbd2` | 2025-05-29 | Canary signals are no longer deduplicated. `filter_dedup` returns early if `signal_instance.canary` is set, and both the default and per-filter dedup queries exclude earlier canary instances (`~SignalInstance.canary`). The windows are unchanged. |
| `7a9fe810` | 2025-06-19 | The default dedup window was hard-coded as `timedelta(hours=1)`. It now comes from the new config `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`, which defaults to 45 and can be overridden by environment variable. The default window changed from 60 to 45 minutes. |
| `086dc910` | 2025-08-07 | `filter_snooze` was simplified to one check: mode must be active and action must be snooze. This looks like a pure cleanup, but it has one behaviour change. An expired snooze filter used to `continue` to the next filter. It now `break`s, so one expired filter stops the check and any later, still-valid snooze filters on that signal are ignored. |
| `917a0b7b` | 2025-08-14 | The commit is titled as a refactor. It adds `_window_start(seconds)` and uses it for both windows. The default window is computed as `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES * 60` seconds, so the result is unchanged. The per-filter window did change. It was `timedelta(minutes=f.window)` and is now `timedelta(seconds=f.window)`. |

**Windows as the code applies them today**
- **Default dedup window:** 45 minutes (2700 s). It applies to signals with no filters at all, and matches any recent instance that has a case, regardless of entities.
- **Per-filter dedup window (`SignalFilter.window`):** seconds. The DB column default is 3600 (1 hour). The pydantic create schema default is 600 (10 minutes).
- **Snooze:** there is no lookback window. A snooze filter applies until its `expiration` timestamp (UTC).

**Likely regression in `917a0b7b`**
- Before it, `f.window` was treated as minutes, although the column comment says seconds. A stored value such as 600 meant 10 hours and now means 10 minutes.
- Every dedup filter's effective window shrank by a factor of 60. Dedup filters therefore stop grouping instances that arrive more than `window` seconds apart, and more cases get opened.
- The commit message doesn't mention this change. Whether the old minutes behaviour or the new seconds behaviour is what filter authors intended is worth confirming.

**Other notes**
- The `filter_signal` docstring still says the default is a 1-hour window. That is stale after `7a9fe810`.
- `4474af25` (2025-06-10) only adds logging to the signal flow. `5e136d7b` (2025-07-03) only adds a model field and a forward-reference rebuild, so I left both out of the table.

I haven't changed any code.

----- next turn -----

Commit `917a0b7b` (2025-08-14, "share the lookback window computation") caused it. It is fixed in the working tree and nothing is committed.

**Cause:** the commit changed the per-filter dedup lookback from `timedelta(minutes=f.window)` to `timedelta(seconds=f.window)`. The UI window picker is labelled "Window (minutes)" and offers 5, 10, 15, 20 and 30, so stored values are minutes. Your filter with window 30 had been a 30-minute lookback. After the commit it became 30 seconds, so two instances 10 minutes apart no longer matched and each opened its own case. The commit was described as a refactor and gave no sign the units had changed. A comment it added claimed the column was in seconds, and that comment was wrong.

**Fix:**
- `src/dispatch/signal/service.py`:
  - `_window_start` now takes minutes.
  - The per-filter call passes `f.window` as minutes again.
  - The default dedup window passes `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` directly, so it stays 45 minutes.
- Existing filters work without being edited, because the stored values were always minutes.
- `src/dispatch/signal/models.py`: the column comment said seconds and the default was `60 * 60`. Read as minutes, that default would be 60 hours, so I changed it to 60 minutes with the comment corrected. It is a Python-side default, so it needs no migration and only affects filters created without a window.

**Test:** `test_filter_actions_deduplicate_window_is_in_minutes` in `tests/signal/test_signal_service.py`. It uses a filter with window 30:
- An earlier instance 10 minutes old gets deduplicated.
- One 40 minutes old does not.

Run with the signal fix reverted, the test fails. With the fix, `tests/signal` gives 33 passed and 1 skipped.

**Pydantic default:** `SignalFilterCreate.window` still defaults to 600. Under minutes that means 10 hours, which was also the behaviour before the regression. I left it alone because the UI always sends a value, but you may want to lower it.

----- next turn -----

Commit `086dc910` (2025-08-07, "simplify snooze filter checks") caused it, and it is fixed in the working tree. Nothing is committed.

**Cause:** the simplification changed the expired-filter branch in `filter_snooze` from `continue` to `break`. If a signal's expired snooze filter is checked before a valid one, the loop stops at the expired one and never reaches the valid one. That is what happened to "Okta: Impossible travel": the filter that expired last week came first, so the one valid until next month was never evaluated. The commit was described as a pure cleanup, so the change wasn't flagged.

**Fix:** `src/dispatch/signal/service.py` now does `continue` again for an expired filter. The loop skips it and keeps checking the remaining filters.

**Test:** `test_filter_snooze_skips_expired_filter_and_applies_valid_one` in `tests/signal/test_signal_service.py`. It gives one signal two snooze filters on the same entity. One expired 7 days ago and is listed first. The other is valid for 30 more days. A new instance for that entity must be snoozed.

**Results:** `tests/signal` gives 34 passed and 1 skipped with the fix. With the signal source changes reverted, the new test fails. That revert also removes the window fix, so the failure is not isolated to this one line.

The test relies on the filters coming back in insertion order. It asserted that order, passed, and I then removed the assertion. It has passed under the local PostgreSQL I ran against. If it ever turns flaky, the filter order is the first thing to check.

----- next turn -----

Here is the recap for the weekly report. Nothing is committed.

**1. Weekly Monday reminders stopped (cases in triage and stable)**
- **Cause:** commit `c509d45e` (2025-08-12, "share the weekly reminder check") moved the Monday check into `_is_reminder_day()` in `src/dispatch/case/scheduled.py`. The helper compares `date.isoweekday()` to `calendar.MONDAY`. `isoweekday()` numbers Monday as 1, while `calendar.MONDAY` is 0, so the check was never true and the weekly reminders silently stopped. The daily triage reminders don't use this check, which is why they kept arriving.
- **Deploy:** the commit reached production in the 2025-08-13 rollout, image `registry.example.com/dispatch:main-81d8ae42`. I confirmed `c509d45e` is an ancestor of that commit. The scheduler and web pods ran `main-b05613b5` before it.
- **First missed Monday:** 2025-08-18. Six case close reminders went out on 2025-08-11. On 2025-08-18 the only reminders in the log are the daily triage reminder and an incident reminder, which is a different job.
- **Fix:** `_is_reminder_day()` now uses `weekday()`. The regression test checks Mondays, non-Mondays and the 2025-08-11 and 2025-08-18 cases.

**2. Nightly `TypeError` in the case close reminder job**
- **Cause:** `case_close_reminder` computed `utcnow() - case.triage_at`, but `triage_at` is NULL for cases that never went through `case_triage_status_flow`. Those cases raised `TypeError`, the per-case `except` logged it, and the case was skipped, so they never got a reminder. The error appears every evening in the log.
- **Fix:** the job now counts from `triage_at`, or from `created_at` when `triage_at` is missing. Four test cases cover the fallback.
- **Stable job:** `case_stable_reminder` already skips cases with no `stable_at`. The log shows its own `TypeError` stopped after 2025-08-12, so the guard went out with the 2025-08-13 deploy. I did not give it the `created_at` fallback.

**3. Signal deduplication and snoozing (same batch of changes)**
- **Dedup windows:** commit `917a0b7b` (2025-08-14) changed the per-filter window from minutes to seconds, so a UI value of 30 became 30 seconds. I restored minutes and fixed the misleading column comment and default. The regression test uses window 30 with instances 10 and 40 minutes old.
- **Snoozing:** commit `086dc910` (2025-08-07) turned `continue` into `break` for an expired snooze filter. An expired filter listed first stopped the loop, so a valid filter after it was never checked. I restored `continue`, and a regression test covers it.
- **Canary signals:** commit `a348bbd2` (2025-05-29) stopped canary signals from being deduplicated. It skips dedup for canary instances and ignores earlier canary instances when matching.
- **Default window:** signals with no filters group instances within 45 minutes. This is configurable through `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`. It was hard-coded at 1 hour before `7a9fe810`, and the `filter_signal` docstring still says 1 hour.
- **Tests:** `tests/signal` gives 34 passed and 1 skipped. The new case-reminder tests pass. The new signal tests fail with the signal fixes reverted.
- **Loose end:** the `SignalFilterCreate.window` pydantic default is still 600, which is 10 hours in minutes.

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