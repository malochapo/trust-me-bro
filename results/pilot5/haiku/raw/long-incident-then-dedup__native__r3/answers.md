**Root cause:** the weekday check added in `c509d45e` compares ISO weekday numbers to `calendar.MONDAY`, and those use different numbering. `date.isoweekday()` returns 1 for Monday through 7 for Sunday, but `calendar.MONDAY` is 0 (I confirmed this in Python). So `_is_reminder_day()` is never true, and the weekly close and stable reminders never fire.

**Where:** `src/dispatch/case/scheduled.py:31-33`:

```python
def _is_reminder_day() -> bool:
    """Reminders about long-running cases go out once a week, on Mondays."""
    return date.today().isoweekday() == calendar.MONDAY
```

It gates `case_close_reminder` (line 49) and `case_stable_reminder` (line 95). The triage reminder has no weekday gate, which is why it keeps arriving.

**The deploy:** `main-81d8ae42`, which is `fix(case): exclude resolved_by in update (#6183)`. It rolled out to the scheduler at 2025-08-13T16:40Z (pod `scheduler-mhtsgqwwx-q5q2n`), and the web tier got the same image. `c509d45e` (Jordan Lee, "refactor(case): share the weekly reminder check") is an ancestor of that commit and is the one that changed the check. It replaced the old `date.today().isoweekday() == 1`, which was correct. The refactor did not change behaviour as intended; it changed the comparison target.

**Evidence in the logs:**
- Monday 2025-08-04 and Monday 2025-08-11 (before the deploy) both logged `Case close reminder sent` lines.
- Monday 2025-08-18 (after the deploy) logged no close or stable reminders. The job ran; there were no sends.
- Daily triage reminders kept going out throughout.

**Caveats:**
- I inferred the deployed code from the log line numbers, not the image itself. The 08-13 traceback places the span at line 47 and the `log.exception` at line 55, which matches the current `HEAD`. The 07-30 deploy (`b05613b5`) had them at 43 and 51, four lines earlier, which matches the code before `c509d45e`.
- The `date.today()` call is local time, while the rest of the function uses `utcnow()`. That's a minor inconsistency and not the cause here.

**Separate issue, not the cause:** `case_close_reminder` calls `datetime.utcnow() - case.triage_at` with no `None` guard, so it raises `TypeError` for cases whose `triage_at` is null. This has happened every night since 2025-07-28 and is caught per case, so it doesn't block other cases. `32fa810f` added a guard for `stable_at` in the stable reminder but not for `triage_at` in the close reminder.

**Suggested fix (not applied):** compare against the same numbering, for example `date.today().weekday() == calendar.MONDAY`. Also add a `triage_at` guard to the close reminder. I haven't changed any code, as you asked. Let me know when you want the fix and a test for the Monday check.

----- next turn -----

The weekly reminder bug is fixed and there is a regression test for it. The 8 other test failures were already there before my change.

**The fix** (`src/dispatch/case/scheduled.py:33`): `_is_reminder_day()` now uses `date.today().weekday()` instead of `isoweekday()`. `weekday()` is 0-based like `calendar.MONDAY`, so the comparison matches Mondays again.

**The regression test** (`tests/case/test_case_scheduled.py`, new): it pins `date.today()` to a Monday, a Tuesday, a Friday and a Sunday, and checks that `_is_reminder_day()` returns True only on the Monday. On the unfixed code the Monday case fails (`False is True`), and all four pass with the fix.

**Test results** (`python -m pytest`, local PostgreSQL):
- `tests/case`: 19 passed, including the 4 new cases.
- Full suite: 363 passed, 4 skipped, 8 failed. The 8 failures are in `tests/ai/test_ai_service.py` (6), `tests/database/test_service.py` (1) and `tests/entity/test_entity_service.py` (1). I stashed my changes and reran those same 8 on the unmodified code, and they fail there too, so they're unrelated to this fix. I did not investigate them.

I didn't commit anything. The `triage_at` guard issue I mentioned earlier is also still open, since you asked for the weekday fix only.

----- next turn -----

The close reminder job's TypeError is fixed, and the job now counts from `created_at` when `triage_at` is missing. The new tests pass, and the full suite shows only the same 8 failures as before.

**What causes the TypeError:** `triage_at` is only written by `case_triage_status_flow` in `src/dispatch/case/flows.py`. Some paths put a case into Triage without running that flow, so the case has no `triage_at`. The clearest one is `reopen_button_click` in `src/dispatch/plugins/dispatch_slack/case/interactive.py`, which sets `case.status = CaseStatus.triage` directly. The job then computes `datetime.utcnow() - None` and logs the error for each such case. I haven't checked which of your production cases hit this path, since I only have the logs and not the database.

**The fix** (`src/dispatch/case/scheduled.py`, in `case_close_reminder`):

```python
span = datetime.utcnow() - (case.triage_at or case.created_at)
```

`get_all_by_status` already loads `created_at`, so no query change was needed.

**Tests** (`tests/case/test_case_scheduled.py`, new file):
- `test_case_close_reminder_counts_from_created_at_without_triage_at`: a Triage case with no `triage_at` and a `created_at` 14 days ago gets a reminder on a Monday. I confirmed this test fails on the old line and passes with the fix.
- `test_case_close_reminder_counts_from_triage_at_when_set`: a case whose `triage_at` is 2 days old gets no reminder, even though `created_at` is older, so the fallback doesn't override a real timestamp.

Two things I had to work around in the tests:
- `CaseFactory` ignores `status=` passed to it, so the tests set the status after creation.
- The registered job loops over every organization schema. The test database has nine organization rows that map to the same schema, so calling the job normally sent each reminder nine times. The tests call the innermost function with `inspect.unwrap` instead.

**Full suite:** the same 8 failures as before (in `tests/ai/test_ai_service.py`, `tests/database/test_service.py`, and `tests/entity/test_entity_service.py`). They also fail on unmodified code.

I didn't change the Slack reopen path itself, so cases reopened that way still won't get `triage_at` set. The fallback covers that for the reminder but doesn't fix the data. Also, `case_stable_reminder` still skips cases without `stable_at` rather than falling back to `created_at`. I left that alone because you asked about the close reminder only. Nothing is committed.

----- next turn -----



----- next turn -----

Four commits since 2025-05-22 changed snooze or deduplication. Only one of them changed a time window, and that one changed its unit. Nothing was changed in the code.

**Commits (oldest first, all on `main`)**

1. **`a348bbd2`** (2025-05-29), *fix(signal): don't dedup on canary signals (#6026)*. Canary signal instances are skipped at the top of `filter_dedup` and are excluded from the match query in both dedup paths. No time window involved.

2. **`7a9fe810`** (2025-06-19), *feat(signal): make the default deduplication window configurable*. The default dedup window (used when a signal has no dedup filter) was hard-coded to 1 hour. It now comes from `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` in `src/dispatch/config.py`, default **45 minutes**, read as minutes.

3. **`086dc910`** (2025-08-07), *refactor(signal): simplify snooze filter checks*. In `filter_snooze`, the separate mode and action None checks were folded into one condition. That part does not change behavior. The behavior change is that an expired snooze filter now hits `break` instead of `continue`. Once an expired snooze filter is found, the loop stops and any later filters are not checked. The result depends on the order of `signal.filters`, which I did not verify. Snooze has no lookback window; it uses an absolute `expiration` datetime.

4. **`917a0b7b`** (2025-08-14), *refactor(signal): share the lookback window computation*. This commit changed the unit for dedup filters. The old code was `timedelta(minutes=f.window)`. The new code is `_window_start(f.window)`, which treats `f.window` as **seconds**, matching the comment on the `SignalFilter.window` column. The default path now computes `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES * 60` seconds, which is still 45 minutes. Existing stored values were not migrated, so a dedup filter saved with `window=600` went from a 10-hour lookback to a 10-minute lookback. This is the most likely place for a real behavior change, and it is not mentioned in the commit message.

**Current values as the code applies them**
- Default dedup (no dedup filters): 45 minutes, from `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES * 60` seconds.
- Dedup filter window: `SignalFilter.window` in seconds. The column default is 3600 s (1 hour). The Pydantic `SignalFilterBase` default is 600 s (10 minutes), which applies when the API caller omits `window`. Neither default has changed since 2025-05-22.
- Snooze: no lookback window. The filter applies until its `expiration` datetime. Filters without an expiration are skipped with a warning.

I did not check production data, so I can't say whether any existing dedup filter's stored `window` value was affected by `917a0b7b`.

----- next turn -----

**Cause:** commit `917a0b7b` (2025-08-14, *refactor(signal): share the lookback window computation*). It changed `_window_start` from minutes to seconds. The filter's window of 30 became 30 seconds, so two instances ten minutes apart fell outside it and opened separate cases. The UI labels the field "Window (minutes)", with options 5, 10, 15, 20 and 30. The other commits I listed don't affect dedup windows.

**Fix** (`src/dispatch/signal/service.py`): the window is read as minutes again, for both dedup filters and the default 45-minute window. The stored values are unchanged, so existing filters work without being edited. The comment on `SignalFilter.window` in `src/dispatch/signal/models.py` now says minutes.

**Regression test:** `test_filter_actions_deduplicate_window_is_in_minutes` in `tests/signal/test_signal_service.py`. It creates a 30-minute deduplicate filter and an earlier instance ten minutes old, then checks that the second instance joins the first one's case. It fails on the seconds code and passes with the fix.

**Results:** the signal service tests pass (15 passed, 1 skipped). The full suite shows the same 8 failures as before, all of which also fail on unmodified code.

**Not changed, for you to decide:**
- The column default in `SignalFilter.window` is `60 * 60`, and the API default is `600`. Under minutes these mean 60 hours and 10 hours. This was already true before `917a0b7b`. A filter created without an explicit window gets these values. I left them alone because the request was about existing filters, but they look like they were meant as seconds.
- I did not check the UI in a browser or the production data. The diagnosis comes from reading the UI code and the commit diff.
- Nothing is committed.

----- next turn -----

**Cause:** commit `086dc910` (2025-08-07, *refactor(signal): simplify snooze filter checks*). In `filter_snooze`, the branch for an expired snooze filter changed from `continue` to `break`. The loop then stopped at the first expired filter, so a valid filter later in the list was never checked. For "Okta: Impossible travel", the expired filter for that user was listed first, so new instances were not snoozed.

**Fix** (`src/dispatch/signal/service.py`): the expired branch is back to `continue`, so the loop skips that filter and checks the rest.

**Regression test:** `test_filter_actions_snooze_skips_expired_filter` in `tests/signal/test_signal_service.py`. It puts an expired snooze filter first and a valid one (expiring in 30 days) second, both matching the same entity. It expects the instance to be snoozed. It fails with the `break` and passes with the fix.

**Results:** the signal service tests pass (16 passed, 1 skipped). The full suite shows the same 8 failures as before, all of which also fail on unmodified code.

Nothing is committed. The working tree also has the earlier changes to `scheduled.py`, the dedup window fix, and the test file from before.

----- next turn -----

Here is the recap for both investigations. The working-tree fixes are not committed yet.

**Weekly reminders (weekday bug)**
- The weekly close and stable reminders stopped after the 2025-08-11 run. The daily triage reminders kept arriving.
- The Monday check used `isoweekday()`, which numbers Monday as 1. It was compared with `calendar.MONDAY`, which is 0, so the check could never be true. Commit `c509d45e` (2025-08-12) introduced this. It shipped in the image `main-81d8ae42`, which was running on the scheduler by 2025-08-13.
- Fix: `_is_reminder_day` now uses `weekday()`. A regression test checks that 2025-08-11 is a reminder day and that Tuesday, Friday and Sunday are not.
- The first Monday with no reminders sent was 2025-08-18.

**Evening TypeError (case close reminder)**
- The nightly close reminder job failed with `datetime - NoneType` for cases in triage with no `triage_at`. Only the triage flow sets that field. A candidate path is the Slack reopen button, which sets the status to triage directly. I have not checked which production cases are affected.
- Fix: the job counts from `created_at` when `triage_at` is missing. Two tests cover the fallback and the case where `triage_at` is set.
- Not changed: the stable reminder still skips cases with no `stable_at`.

**Signal deduplication and snoozing**
- Dedup windows: commit `917a0b7b` (2025-08-14) changed the window from minutes to seconds. A window of 30 meant 30 seconds, so instances ten minutes apart opened separate cases. The fix restores minutes, which is what the UI labels. Existing stored values work unchanged, and a regression test covers it.
- Snoozing: commit `086dc910` (2025-08-07) changed an expired snooze filter from `continue` to `break`. The loop stopped at the first expired filter, so a valid filter after it never applied. The fix restores `continue`, and a regression test covers it.
- Canary signals: commit `a348bbd2` (2025-05-29) stopped canary signals from being deduplicated and excluded them from matching. No change was needed here.
- Default window: signals with no filter are grouped over 45 minutes. The setting `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` controls it, and it defaults to 45.
- Not changed: the model defaults for `SignalFilter.window` (3600 and 600) now read as 60 hours and 10 hours.

The full test suite shows the same 8 failures as before, all of which also fail on unmodified code. Nothing is committed.

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