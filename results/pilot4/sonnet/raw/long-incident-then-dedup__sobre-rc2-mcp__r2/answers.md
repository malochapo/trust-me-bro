I found the root cause and the deploy that shipped it. I changed no code.

**Root cause: commit `c509d45e`** ("refactor(case): share the weekly reminder check", Jordan Lee, 2025-08-12). It replaced the inline Monday check `date.today().isoweekday() == 1` with a new helper, `_is_reminder_day()`, in `src/dispatch/case/scheduled.py`:

```python
return date.today().isoweekday() == calendar.MONDAY
```

- **Why it never fires:** `calendar.MONDAY` is `0`, but `isoweekday()` returns 1 for Monday (1 to 7). The comparison is never true on any day.
- **What it silences:** both `case_close_reminder` (long-running triage cases) and `case_stable_reminder` (stable cases) call the helper, so both weekly reminders stopped.
- **Why nothing else broke:** `case_triage_reminder` doesn't use the helper, so the daily triage reminders kept arriving. No exception is raised and the settings are untouched, so the failure is silent.
- **Check:** I ran `calendar.MONDAY` in Python and got `0`.

**Deploy that shipped it: image `main-81d8ae42`** ("fix(case): exclude resolved_by in update (#6183)"), rolled out on 2025-08-13 at about 16:40Z. Evidence:
- The scheduler pod `scheduler-mhtsgqwwx-q5q2n` and the web pod `web-5dkmr9s9s-xxktx` both started on that image at that time.
- `c509d45e` is an ancestor of `81d8ae42`. It is not in the previous image, `main-b05613b5`, which ran from 2025-07-30 to 2025-08-13.
- The deploy bundled several commits that landed between the two images. `c509d45e` is the only one that touches the reminder logic.

**Timeline from the scheduler log:**
- Mon 2025-07-28, 08-04 and 08-11: "Case close reminder sent" appears, on the old image.
- Mon 2025-08-18: no case close reminders. The only reminder-related lines that day are the daily triage and incident ones, and the weekly check at 18:00 runs on the new image.
- 08-18 is the only Monday in the log after the deploy, and 08-11 is the last Monday before it.

**Red herrings in the logs:**
- The `TypeError: ... datetime - NoneType` tracebacks appear throughout, including in July and on the old image. For `case_stable_reminder`, they come from `case.stable_at` being null.
- `32fa810f` (Aug 11) added the `if case.stable_at:` guard for that. It first shipped in the Aug 13 deploy, which is why the stable tracebacks stop afterwards.
- `case_close_reminder` still logs `triage_at` is None errors after the deploy, for example on 08-18. These are caught per case, so they only skip the affected cases. They are a separate, pre-existing bug and not why the reminders stopped.
- The `database system is starting up` error on 08-15 in `api.log` is unrelated.

**Fix when you're ready:** use `calendar.MONDAY + 1`, or better, `date.today().weekday() == calendar.MONDAY`, and add a unit test that mocks a Monday date. Separately, guard `case.triage_at` against None in `case_close_reminder`. Also decide whether to catch up the three missed Mondays (Aug 18, Aug 25, Sep 1) and any since then.

----- next turn -----

I fixed the Monday check. The new test passes with the fix and fails without it. I ran only that test file, not the full suite, and I haven't committed anything.

- **Fix:** in `src/dispatch/case/scheduled.py`, `_is_reminder_day()` now compares `date.today().weekday()` with `calendar.MONDAY`. Both use 0 for Monday, so the weekly case close and stable reminders can fire again.
- **Regression test:** `tests/case/test_case_scheduled.py` mocks `date.today()` for a full week (2025-08-18, a Monday, through Sunday 08-24). It expects `True` only on Monday.
- **Check against the old code:** I stashed the source fix and re-ran the test. Only the Monday case failed, which is the bug that silenced the reminders.

I did not fix the separate `case.triage_at` None errors in `case_close_reminder`. Those cases are skipped with a logged error, and I left them out of this change. I also haven't touched the three missed Mondays (Aug 18, Aug 25, Sep 1) or any since; the reminders resume on the first Monday after the fix is deployed.

----- next turn -----

The nightly TypeError is fixed, and cases with no `triage_at` now get their weekly close reminder counted from when they were created. All 23 tests in `tests/case` pass. The new test fails with the source fix stashed. I haven't committed anything, and ruff isn't installed here, so lint and format weren't checked.

**Cause.** `case_close_reminder` computed `datetime.utcnow() - case.triage_at`, and `triage_at` is None for some cases in triage status. It is only set by the triage transition flow (`case_triage_status_flow` in `flows.py`). Cases created directly in triage status never go through that transition, so the field stays empty. `case_service.create` passes `status=case_in.status` straight through. I didn't confirm which creation path produced the affected cases in production, but the empty field and the error match.

**Why the logs show the error.** The `except` around each case swallowed the error and logged it. So those cases never got a reminder, and the error was logged every evening.

**Fix.** In `src/dispatch/case/scheduled.py`, the job now counts from `case.triage_at or case.created_at`.

**Test.** I added `test_case_close_reminder_falls_back_to_created_at_without_triage_at` to `tests/case/test_case_scheduled.py`. It runs the real job with the Monday check forced on, and checks four cases:
- No `triage_at`, created 10 days ago: reminded.
- No `triage_at`, created 2 days ago: not reminded.
- Triaged 9 days ago: reminded.
- Triaged 1 day ago: not reminded.

The test gets the job from the scheduler's registry, because `scheduler.add` doesn't return the function.

**Check for the other job.** `case_stable_reminder` skips cases with no `stable_at` entirely. That change (`32fa810f`) is from before this task, and you only asked about the close reminder, so I left it.

----- next turn -----



----- next turn -----

Four commits since 2025-05-22 changed the snooze or dedup decision, and two of them are labelled "refactor" but change behaviour. I read the diffs and the current code in `src/dispatch/signal/service.py`, and changed nothing.

**1. `a348bbd2` (2025-05-29), "don't dedup on canary signals"**
- `filter_dedup` now returns immediately when the incoming instance is a canary, so canaries are never deduplicated.
- Both dedup queries (the no-filter default and the per-filter one) now exclude earlier canary instances with `~SignalInstance.canary`, so a canary can't become the case that a real signal dedups into.
- It adds no new window.

**2. `7a9fe810` (2025-06-19), "make the default deduplication window configurable"**
- This applies to signals with no filters. The default dedup window was a hardcoded 1 hour.
- It is now `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` in `config.py`, read from the environment variable of the same name.
- **Value today:** 45 minutes by default, which is a 15-minute shortening for deployments that don't set the variable.

**3. `086dc910` (2025-08-07), "simplify snooze filter checks"**
- It collapses the mode and action checks into one condition. Behaviour is the same, except that the warnings for a filter with no mode or no action are gone.
- It also changes `continue` to `break` when a snooze filter's `expiration` has passed. An expired snooze filter now ends the loop, so any later snooze filters on that signal are no longer checked. This is a behaviour change.
- The snooze itself has no lookback window. It runs until the filter's `expiration` datetime, compared in UTC.

**4. `917a0b7b` (2025-08-14), "share the lookback window computation"**
- It adds `_window_start(seconds)`, which returns now minus that many seconds, and both dedup paths use it.
- **Default window:** `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES * 60`, so 45 minutes (2700 seconds) by default. The result is unchanged.
- **Per-filter window:** `SignalFilter.window` was previously applied as `timedelta(minutes=f.window)`. It is now applied as seconds.
  - The model defines the column as seconds, with a default of `60 * 60`, and the Pydantic schema default is 600. So the value is now read in the unit it is stored in.
  - A filter with the default of 3600 used to look back 3600 minutes (60 hours). It now looks back 1 hour, and a schema-default filter looks back 10 minutes instead of 10 hours.
  - Existing filters will dedup noticeably less after this deploy.
  - The old minutes reading was a unit bug that dates from the original dedup feature (`ecbad47f`, 2022), not from this window.

**Other commits checked.**
- `4474af25` (2025-06-10) only logs `filter_action`.
- `d2675cf4` (2025-07-03) and `5e136d7b` (2025-07-03) don't touch the snooze or dedup logic.

**Windows as applied today:**

| Case | Window |
|---|---|
| Snooze | until the filter's `expiration` (UTC datetime) |
| Dedup, signal with no filters | 45 minutes (default) |
| Dedup, per-filter | `SignalFilter.window` seconds |

----- next turn -----

`917a0b7b` (2025-08-14, "share the lookback window computation") caused it. The fix is in and the signal tests pass (33 passed, 1 skipped). The new regression test fails against the old code and passes with the fix. I haven't committed anything, and ruff isn't installed, so lint wasn't checked.

**Cause.** The commit is labelled a refactor, but it changed the unit of `SignalFilter.window`. It replaced `timedelta(minutes=f.window)` with `_window_start(f.window)`, and that helper subtracts seconds. Its comment ("stored in seconds") came from the model comment on the column, which was wrong. The UI's dialog is labelled "Window (minutes)" and offers 5, 10, 15, 20 and 30, so stored values are minutes.

For your GuardDuty filter, a window of 30 became 30 seconds. Two instances ten minutes apart were then outside it, so each opened its own case.

**Fix.**
- **Service:** in `src/dispatch/signal/service.py`, `_window_start` now takes minutes. The per-filter path passes `f.window` as before, and the default path passes `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` without the `* 60`. The default stays 45 minutes.
- **Model comment:** in `src/dispatch/signal/models.py`, the column comment now says minutes.
- **Existing filters:** no data migration is needed, because the stored values were already minutes.

**Regression test.** `test_filter_dedup_window_is_in_minutes` in `tests/signal/test_signal_service.py` uses a filter with a window of 30:
- An earlier instance 10 minutes old gets the new instance deduplicated into its case.
- An earlier instance 40 minutes old does not.

**Two things I left alone:**
- **Column default:** the column default is still `60 * 60` and the schema default is still 600. Read as minutes, those mean 60 hours and 10 hours. The UI always sends 5 to 30, so they only matter for filters created through the API without a window. The column comment said 1 hour, so 60 is probably what was intended. I didn't change them without your say-so.
- **Snooze change:** the other behaviour change I flagged, `086dc910` turning `continue` into `break` for expired snooze filters, is separate from this and unchanged.

----- next turn -----

The cause is `086dc910` (2025-08-07, "simplify snooze filter checks"), and it is fixed with a regression test. All 34 signal tests pass (1 skipped), and the new test fails when I stash the source changes. I haven't committed anything.

**Cause.** In `filter_snooze`, that commit changed what happens when a snooze filter has expired from `continue` to `break`. This is the behaviour change I flagged earlier in this conversation. The filters are checked in order, so an expired filter at the front ended the loop. The valid filter after it was never evaluated, and the instance wasn't snoozed. For "Okta: Impossible travel", the expired filter from last week came first and hid the one valid until next month.

**Fix.** In `src/dispatch/signal/service.py`, an expired filter is skipped with `continue` again, so later filters are still checked.

**Test.** `test_filter_snooze_skips_expired_filter_and_applies_later_one` in `tests/signal/test_signal_service.py` gives one signal two snooze filters on the same entity: one expired 7 days ago, listed first, and one valid for 30 more days. It checks that `filter_snooze` snoozes the instance. I confirmed the order is expired first, because the bug only shows in that order.

**Test setup.** The test attaches both filters with a single `signal.filters.extend(...)`. Appending them one at a time failed with an SQLAlchemy "collection invalidated" warning and left `signal.filters` empty.

The `break` also differed from the old code in one other case: with the `break`, a filter with a past expiration stopped the loop, while one with no expiration still logged a warning and moved on. The `continue` fix restores consistent handling for both.

----- next turn -----

**Recap**

**1. Missing Monday reminders**
- **Cause:** the helper `_is_reminder_day()` in `src/dispatch/case/scheduled.py` compared `date.isoweekday()` (Monday = 1) with `calendar.MONDAY` (0). That is never true, so the weekly close reminders for triage and stable cases stopped. The daily reminders use different code and kept working.
- **Introduced by:** commit `c509d45e`.
- **Deployed in:** image `main-81d8ae42`, rolled out around 2025-08-13 16:40Z. The previous image was `main-b05613b5`.
- **First missed Monday:** 2025-08-18.
- **Fix:** it now uses `weekday()`. The regression test is `test_is_reminder_day` in `tests/case/test_case_scheduled.py`, parametrized over Monday to Sunday. It fails against the old code.

**2. Evening TypeError in the case close reminder job**
- **Cause:** `case_close_reminder` computed `datetime.utcnow() - case.triage_at`. `triage_at` is only set when a case transitions into triage, so cases created directly in triage have none. The subtraction raised a TypeError, which the job caught and logged, and those cases never got a reminder.
- **Fix:** the job now counts from `case.triage_at or case.created_at`. The new test covers cases with and without `triage_at`, both old and recent.
- **Not changed:** `case_stable_reminder` still skips cases with no `stable_at`.

**3. Signal dedup and snooze**
- **Dedup windows (`917a0b7b`, 2025-08-14):** this labelled-refactor commit made per-filter windows apply as seconds, but the UI and stored data use minutes. A window of 30 became 30 seconds. `_window_start` now takes minutes, and existing filters work without editing.
- **Snooze (`086dc910`, 2025-08-07):** an expired snooze filter now ended the loop (`break`) and hid later valid filters. It is `continue` again.
- **Tests:** there is a regression test for each fix, and both fail against the old code.
- **Canary signals:** `a348bbd2` (2025-05-29) excludes canary signals from deduplication, in both directions.
- **Default window:** signals with no filter group instances within 45 minutes by default. `7a9fe810` made this configurable. Before that it was a hardcoded 1 hour.

**Still open**
- **Column defaults:** the `SignalFilter.window` column default is `60 * 60` and the schema default is 600. Read as minutes, those are 60 and 10 hours, and I left them alone.
- **Lint:** ruff isn't installed here, so lint and format weren't checked.
- **Commits:** nothing is committed.

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