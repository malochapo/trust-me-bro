## Root cause

Commit `c509d45e`, "refactor(case): share the weekly reminder check" (Jordan Lee, 2025-08-12), broke the Monday check.

The refactor replaced the inline check `date.today().isoweekday() == 1` with a new helper in `src/dispatch/case/scheduled.py:31`:

```python
def _is_reminder_day() -> bool:
    return date.today().isoweekday() == calendar.MONDAY
```

The two functions use different numbering for weekdays:
- `isoweekday()` returns 1 for Monday through 7 for Sunday.
- `calendar.MONDAY` is 0, because the `calendar` module counts from Monday = 0. I confirmed this by running it.

So `_is_reminder_day()` can never be true. Both `case_close_reminder` (triage cases) and `case_stable_reminder` (stable cases) gate on it (lines 49 and 95), so neither sends anything any more. The daily triage reminder (`case_triage_reminder`) doesn't use the helper, which is why it still works. Nothing raises an error, which is why the failure was silent.

## Evidence in the logs

- **Mon 2025-07-28 and 2025-08-04:** "Case close reminder sent to …" appears for 4 and 6 assignees at 18:00.
- **Mon 2025-08-11:** 5 close reminders went out at 18:00. This was the last working Monday.
- **Mon 2025-08-18:** `case_close_reminder` and `case_stable_reminder` ran but sent nothing. The "Incident close reminder" still went out, since incidents use different code.
- Every other day in the range shows only triage reminders.

## The deploy

The deploy is image `registry.example.com/dispatch:main-81d8ae42`, rolled out on **2025-08-13 at about 16:40Z**. The kubelet log shows both pods starting with it:
- Scheduler pod `scheduler-mhtsgqwwx-q5q2n` replaced `scheduler-xdp7k6gs2q-w6cj7` at 16:40:06.
- Web pod `web-5dkmr9s9s-xxktx` replaced `web-bsnvb5wc2t-7lt2t` at 16:40:07.

`81d8ae42` is "fix(case): exclude resolved_by in update (#6183)", dated 2025-08-12. `git merge-base --is-ancestor` confirms it contains `c509d45e`.

The previous image, `main-b05613b5`, had been running since 2025-07-30 and does not contain the refactor. Between those two images the refactor was the only change to the reminder code.

## Separate noise in the logs

Both reminder jobs log `unsupported operand type(s) for -: 'datetime' and 'NoneType'` every day, from before the deploy. `case_close_reminder` subtracts `case.triage_at` without a None check, and `case_stable_reminder` had the same problem until `32fa810f` (the check was in the image running the whole time). It is caught per case and is not what stopped the Monday reminders, but it means some cases are skipped. It is worth fixing alongside the main fix.

## Suggested fix (not applied)

Use `calendar.MONDAY` consistently, for example `date.today().weekday() == calendar.MONDAY`. Alternatively, compare `isoweekday()` to 1 as before. A small unit test that mocks Monday and Tuesday would have caught this.

I haven't changed any code.

----- next turn -----

I fixed the Monday check and added a regression test. The new tests pass with the fix. With the fix reverted, the three Monday cases fail, so the test catches the bug. The rest of `tests/case` passes (26 tests).

- **The fix:** in `src/dispatch/case/scheduled.py`, `_is_reminder_day()` now compares `date.today().weekday()` to `calendar.MONDAY`. Both sides count Monday as 0. Before, `isoweekday()` counted Monday as 1 against `calendar.MONDAY` = 0, so the check was never true.
- **The tests:** the new file is `tests/case/test_case_scheduled.py`. It checks `_is_reminder_day()` against every day of the week, using a fixed week that starts on Monday 2025-08-18. It also runs the close-reminder and stable-reminder jobs with a case older than a week, and checks the reminder is sent on a Monday and not on a Tuesday.

The jobs are unwrapped by their scheduler names to reach the function body, because the scheduler decorator doesn't return the function. The tests mock the date, so they don't depend on when they run.

I didn't touch the separate `triage_at` None error that `case_close_reminder` logs every day, and I haven't committed anything.

----- next turn -----

I fixed the TypeError in the case close reminder job and added a test for it. `tests/case` now passes (27 tests), and the new test fails when the fix is reverted.

**Cause.** `case_close_reminder` computes `datetime.utcnow() - case.triage_at`, and `triage_at` is `None` for some triage cases. The job only gets `triage_at` set when a case moves into triage through the status-change flow (`case_triage_status_flow`, `src/dispatch/case/flows.py:594`). A case created directly in triage never goes through that flow, so it has no `triage_at`. A case that was already in triage before `triage_at` was tracked would have none either. I couldn't tell from the logs which of these applies to your cases. The job's per-case try/except caught the error each evening, so those cases were silently skipped. The 18:00 tracebacks in `scheduler.log` match this (`case_close_reminder:51`, line 43 in the deployed build).

**Fix.** In `src/dispatch/case/scheduled.py`, the job now counts from `case.triage_at or case.created_at`. These cases now get their Monday reminder once they are older than a week.

**Test.** `test_case_close_reminder_falls_back_to_created_at_without_triage_at` in `tests/case/test_case_scheduled.py` uses a triage case with `triage_at=None` that was created 10 days ago. On a Monday, it checks that the reminder is sent and that no error is logged.

`case_stable_reminder` has a similar gap. It skips cases with no `stable_at` without logging anything, so those never get a reminder either. I left it alone because you only mentioned the close reminder. Say so if you want the same `created_at` fallback there.

I haven't committed anything.

----- next turn -----



----- next turn -----

Five commits since 2025-05-22 change how a new signal instance gets snoozed or deduplicated. I read the diffs and the current code in `src/dispatch/signal/service.py`. I haven't run anything or changed any code.

**`a348bbd2` (2025-05-29): don't dedup on canary signals (#6026)**
- `filter_dedup` now returns early for canary instances, so they are never deduplicated.
- Existing canary instances are also excluded from the candidate matches, both in the no-filter default path and in the per-filter path.
- It changed no window values.

**`7a9fe810` (2025-06-19): make the default deduplication window configurable**
- This is the window used when a signal has no filters at all. It was a hard-coded 1 hour.
- It now reads `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`, added to `config.py`. It is an int in minutes and defaults to 45.
- With no environment override, the default window went from 60 minutes to 45.

**`086dc910` (2025-08-07): simplify snooze filter checks**
- It was presented as a refactor, but it changes behaviour in `filter_snooze`. It does not touch the 45-minute window or any other time window.
- It drops the "no mode" and "no action" warnings. Such filters are now skipped without a log line.
- An expired snooze filter (`expiration <= now`) used to `continue` to the next filter. It now does `break`, which stops the loop. Any filter after an expired one in iteration order is no longer checked, so a still-active snooze after it is ignored.
- A snooze filter with no `expiration` is still skipped with a warning.
- Snooze is bounded by the filter's `expiration` timestamp, not by a window.

**`917a0b7b` (2025-08-14): share the lookback window computation**
- It also presents as a refactor, but it changes a window unit. It adds a `_window_start(seconds)` helper that returns now minus that many seconds.
- Default path: `_window_start(SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES * 60)`. This is still 45 minutes, so nothing changed here.
- Per-filter path: the window used to be `timedelta(minutes=f.window)`. It is now `_window_start(f.window)`, so `f.window` is read as seconds.
- `SignalFilter.window` has been an integer number of seconds since it was added in 2023 (`# number of seconds ... default to 1 hour`). The schema default is `600`, and the DB default is `3600`.
- Before this commit, the per-filter code treated seconds as minutes, so the lookback was 60 times too long. A 600 filter looked back 600 minutes (10 hours) and a 3600 filter looked back 60 hours.
- Today a filter with `window=600` looks back 10 minutes and the DB default of 3600 looks back 1 hour. Existing filters will now dedup against far fewer past instances than they did before 2025-08-14.

**Current values**

| Case | Window | Unit |
|---|---|---|
| Signal with no filters | `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`, default 45 | minutes, converted to seconds in code |
| Signal with dedup filters | `SignalFilter.window` per filter, schema default 600, DB default 3600 | seconds |
| Snooze | the filter's `expiration` timestamp | no window |

`4474af25` (2025-06-10) only adds `log.info` lines in `signal/flows.py` about the filter outcome. It changes no decision logic. Three other commits that touched the signal code (`01c28ff0`, `5e136d7b`, `90f73fe2`) have no snooze, dedup, window or expiration changes in `service.py`.

I only checked `src/`. `917a0b7b` raises a question you may want to settle: whether the old minutes behaviour was relied on in production. The commit message calls it a refactor.

----- next turn -----

Commit `917a0b7b` (2025-08-14, "share the lookback window computation") caused it. I fixed `filter_dedup` and added a regression test. With the fix, `tests/signal` and `tests/case` pass together (60 passed, 1 skipped). With the signal source changes stashed, the new test fails.

**Cause.** `917a0b7b` made deduplication filters read `SignalFilter.window` as seconds, because the model comment said so. In practice the window has always been minutes. The old code used `timedelta(minutes=f.window)`, and the UI field is labelled "Window (minutes)" with choices 5, 10, 15, 20 and 30. The model comment was stale.

For "GuardDuty: Unauthorized API call", a window of 30 became 30 seconds. Two instances ten minutes apart no longer matched, so each opened its own case.

**Fix.**
- **`src/dispatch/signal/service.py`:** `_window_start` now takes minutes. The per-filter path uses `f.window` as minutes again, and the no-filter default path passes `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` directly (it had been multiplying by 60).
- **`src/dispatch/signal/models.py`:** I corrected the stale "seconds" comment.
- **No migration:** the stored values were minutes all along, so existing filters work without being edited.

**Test.** `test_filter_actions_deduplicate_window_is_in_minutes` in `tests/signal/test_signal_service.py` uses a filter with `window=30` and checks two cases:
- An instance from 10 minutes ago is deduplicated into its case.
- An instance from 40 minutes ago is not.

The test attaches the filter by creating it and then calling `signal_filter.signals.append(signal)`. Appending to `signal.filters` left that collection empty in my first attempt, so the test was silently falling back to the 45-minute default window. If other tests in that file use `signal.filters.append(...)` the same way, their filters may not be applied either. I didn't check them.

**Not changed.** The column default is 3600 and the schema default is 600. Read as minutes, those are 60 hours and 10 hours. Those defaults predate this regression and only apply to filters created without a window. Say if you want them changed.

Nothing is committed.

----- next turn -----

The cause is in `filter_snooze`, and it comes from the same batch of changes. It is `086dc910` (2025-08-07, "simplify snooze filter checks"), the one I flagged earlier as a behaviour change.

**Cause.** The loop used to `continue` past a snooze filter that had expired. The refactor turned that into `break`, which stops the whole loop. For "Okta: Impossible travel", the expired filter is evaluated first, so the loop ends there. The valid filter after it is never checked, and the instance is not snoozed. The result depends on filter order, which is why only some signals were hit.

**Fix.** In `src/dispatch/signal/service.py`, I changed the `break` on an expired filter back to `continue`. I left the other changes from that commit alone. They only drop the "no mode" and "no action" warnings, and those filters are still skipped.

**Test.** `test_filter_snooze_skips_expired_filter_and_applies_later_active_one` in `tests/signal/test_signal_service.py` attaches two snooze filters to a signal. The expired one (a week ago) comes first and the valid one (30 days ahead) second. It asserts that an instance is snoozed.

With the `src/dispatch/signal` changes stashed, the new test fails. With the changes in place, `tests/signal` passes (34 passed, 1 skipped). I did not run `tests/case` this time.

I attached the filters with `signal_filter.signals.append(signal)`, as in the previous test, because appending to `signal.filters` leaves that collection empty. The test asserts both filters are attached, so it can't pass by accident.

Nothing is committed. Three uncommitted fixes sit in the working tree: the weekday bug in the case reminders, the dedup window units, and this snooze fix.

----- next turn -----

Here is the recap of both investigations. All fixes are in the working tree and nothing is committed.

## Investigation 1: missing Monday reminders and the evening TypeError

**Missing weekly reminders.**
- **Cause:** `_is_reminder_day()` in `src/dispatch/case/scheduled.py` compared `date.today().isoweekday()` with `calendar.MONDAY`. `isoweekday()` counts Monday as 1 and `calendar.MONDAY` is 0, so the check was never true on a Monday. The weekly close reminders for long-running triage and stable cases were therefore skipped, while the daily triage reminders kept working.
- **Introduced by:** `c509d45e`.
- **Deploy:** image `main-81d8ae42`, started on 2025-08-13 at about 16:40Z (a Wednesday). The first Monday after that was 2025-08-18, so that is the first Monday whose reminders were not sent.
- **Fix:** the check now uses `weekday()`, where Monday is 0.
- **Tests:** `tests/case/test_case_scheduled.py` checks that both weekly jobs send only on Monday.

**Evening TypeError.**
- **Cause:** `case_close_reminder` computes `utcnow() - case.triage_at`, and `triage_at` is `None` for cases that never went through the triage transition flow. The per-case error handling logged the TypeError each evening and skipped those cases.
- **Fix:** the job now counts from `case.triage_at or case.created_at`.
- **Test:** a triage case with `triage_at=None` and `created_at` 10 days ago still gets its reminder, with no error logged.
- **Open point:** `case_stable_reminder` skips cases with no `stable_at` silently. I left it alone, and it could take the same fallback if you want.

## Investigation 2: signal snooze and deduplication

I listed the commits since 2025-05-22 that changed snooze or deduplication, then fixed two regressions that came from them.

- **`a348bbd2`** (2025-05-29): canary signals are no longer deduplicated, and existing canary instances are ignored as dedup candidates.
- **`7a9fe810`** (2025-06-19): the default dedup window for signals without filters, previously a hard-coded 1 hour, became configurable. It is now 45 minutes by default.
- **`086dc910`** (2025-08-07): snooze regression. An expired snooze filter now did `break` instead of `continue`, so any valid filter after it was never checked. I restored `continue` and added a test.
- **`917a0b7b`** (2025-08-14): dedup window regression. It read `SignalFilter.window` as seconds, but it has always been minutes, which is what the UI says. A window of 30 became 30 seconds. I restored minutes in `src/dispatch/signal/service.py` and added a test. I also corrected the stale model comment.
- **Defaults not changed:** the column default (3600) and the schema default (600) are still in place. Read as minutes, they are long windows (60 hours and 10 hours).
- **Existing tests:** some existing tests append filters with `signal.filters.append(...)`, which left the collection empty in my attempts. They may be passing without the filter applied. I didn't check them.

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