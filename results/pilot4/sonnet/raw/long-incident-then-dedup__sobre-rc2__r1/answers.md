**Root cause:** commit `c509d45e` ("refactor(case): share the weekly reminder check", Jordan Lee, 2025-08-12) broke the Monday check in `src/dispatch/case/scheduled.py`.

- **Before:** `date.today().isoweekday() == 1`. `isoweekday()` returns 1–7 with Monday = 1, so this was correct.
- **After:** a new helper, `_is_reminder_day()`, compares `isoweekday()` to `calendar.MONDAY`. In the `calendar` module Monday is **0** (I checked), and `isoweekday()` never returns 0. The helper is therefore always False.

Both `case_close_reminder` (long-running triage cases) and `case_stable_reminder` (stable cases) use that helper. Both silently stopped sending. No error is logged, because the `if` is simply never true. The daily triage reminder (`case_triage_reminder`) doesn't use the helper, so it kept working, which matches what you saw.

**Evidence from the logs:**
- "Case close reminder sent" appears on Mondays 07-28 (4), 08-04 (6) and 08-11 (5), and never on Monday 08-18.
- The 08-18 jobs still run (their elapsed-time lines are logged), but they send nothing.
- 08-11 was the last Monday before the new code went live.

**The deploy:** production rolled on **2025-08-13 at about 16:40 UTC**.
- The scheduler pod changed from `scheduler-xdp7k6gs2q-w6cj7` to `scheduler-mhtsgqwwx-q5q2n`, and "Starting scheduler..." is logged at 16:40:11.
- The API pod changed from `web-bsnvb5wc2t-7lt2t` to `web-5dkmr9s9s-xxktx` at the same time.
- Line numbers in the scheduler tracebacks shift after the deploy (`case_close_reminder` line 39 → 47). That shows the refactored file was running.

The logs don't name a release tag or commit hash. The commit I'm pinning it on is inferred from the timing and the line-number shift. The 08-13 rollout most likely also carried `32fa810f` (the `stable_at` fix, 08-11) and the `resolved_by` commits `bce2fca2` and `81d8ae42` (08-12). Only `c509d45e` touches the Monday logic.

**Unrelated noise:** the `datetime - NoneType` errors in `case_close_reminder` and `case_stable_reminder` appear in every run since 07-28. Cases with no `triage_at` or `stable_at` hit them. The exception is caught per case, so these errors don't cause the missing reminders.

**Suggested fix, not applied:** make `_is_reminder_day()` compare against `calendar.MONDAY` using `date.today().weekday()`, or go back to `isoweekday() == 1`. A small unit test for the helper would have caught this.

Reminders for Mondays 08-18 and later were never sent. Decide whether to send a catch-up round once the fix is deployed.

----- next turn -----

The Monday check is fixed. In `src/dispatch/case/scheduled.py`, `_is_reminder_day()` now uses `date.today().weekday() == calendar.MONDAY`. `weekday()` counts Monday as 0, which matches `calendar.MONDAY`.

I added `tests/case/test_case_scheduled.py`, which checks that Monday 2025-08-18 is a reminder day and that each of the other six days is not. The seven checks pass with the fix. With the fix stashed, the Monday check fails, so the test would have caught the bug. I only ran this new test file, not the full suite.

Nothing is committed. The weekly reminders will only resume after this is deployed. The Mondays missed since 08-18 still need the catch-up decision I mentioned earlier.

----- next turn -----

The nightly `TypeError` is fixed, and the cases that caused it now get their weekly reminder. All 8 tests in `tests/case/test_case_scheduled.py` pass. Nothing is committed.

**Cause:** `case_close_reminder` computes `datetime.utcnow() - case.triage_at`. `triage_at` is only set in `case_triage_status_flow` (`src/dispatch/case/flows.py:594`), when a case moves through the triage transition. Cases that are in triage status without having gone through that transition have `triage_at = NULL`. The subtraction raises `TypeError` for them, the per-case `except` logs it, and they never get a reminder.

**Fix:** in `src/dispatch/case/scheduled.py`, the job now counts from `case.triage_at or case.created_at`.

**Test:** `test_case_close_reminder_falls_back_to_created_at` runs the real job with stubbed cases and Monday forced on.
- A case with no `triage_at` created 10 days ago gets a reminder.
- A case with no `triage_at` created 2 days ago does not.
- A case triaged 8 days ago gets a reminder, and one triaged 1 day ago does not.
- No exception is logged.

With the source changes stashed, it fails as expected.

`case_stable_reminder` has the same missing-timestamp problem for `stable_at`. It already skips those cases quietly (`32fa810f`), so it logs no error, but those cases still never get a reminder. You only asked about the close reminder, so I left it alone. If you want it to fall back to `created_at` too, I can add that.

----- next turn -----



----- next turn -----

Four commits since 2025-05-22 changed how Dispatch decides whether a new signal instance is snoozed or deduplicated. Two more look related but don't change that decision. I read the commits and the current code in `src/dispatch/signal/service.py` and `config.py`. I made no code changes.

**The four commits**

1. `a348bbd2` (2025-05-29, #6026), "don't dedup on canary signals":
   - `filter_dedup` now returns right away for canary instances, so they are never deduplicated.
   - Canary instances are also excluded from the lookback queries, both the default one and the per-filter one, so a canary can't be the instance that something else is deduplicated against.
   - This adds no time window.

2. `7a9fe810` (2025-06-19), "make the default deduplication window configurable":
   - The default window applies to signals that have no filters at all. It used to be hard-coded at 1 hour.
   - It now comes from `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` in `config.py`, with a default of **45 minutes**, not the old 60.
   - So the default window shrank from 60 to 45 minutes unless the environment variable is set. The commit message doesn't mention the change in default.
   - The docstring of `filter_signal` still says "1-hour window".

3. `086dc910` (2025-08-07), "simplify snooze filter checks":
   - It merges the mode and action checks in `filter_snooze` into one condition and drops the two "has no mode" and "has no action" warnings.
   - It also changes what happens to an expired snooze filter. An expired filter (`expiration <= now`) used to `continue` to the next filter. It now does `break`.
   - Today, an expired snooze filter stops the loop, so any later snooze filter on the same signal is never evaluated. That later filter could still be active.
   - This is a behaviour change inside a commit labelled a refactor.
   - The snooze window is the filter's `expiration` timestamp, compared in UTC. It is not a duration.

4. `917a0b7b` (2025-08-14), "share the lookback window computation":
   - It adds `_window_start(seconds)`, which returns now (UTC) minus that many seconds.
   - The default window is now computed as `_window_start(SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES * 60)`, which is still 45 minutes.
   - The per-filter window changed from `timedelta(minutes=f.window)` to `_window_start(f.window)`. A comment says `SignalFilter.window` is stored in seconds.
   - The model agrees: `window` is an `Integer` of seconds, default `60*60`. The Pydantic default is 600, which is 10 minutes.
   - So the code now treats `f.window` as seconds, which matches the model. The old code treated it as minutes, which was a 60× overstatement. Any filter whose stored window was entered as minutes will now cover a much shorter span than before.

**Windows as the code applies them today**

| Case | Window |
|---|---|
| Signal with no filters | 45 minutes by default, from `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`; the config is in minutes and is converted to seconds internally |
| Signal with a dedup filter | `f.window` seconds, DB default 3600 s (1 hour), schema default 600 s (10 minutes) |
| Snooze filter | Active until `expiration` (UTC timestamp), no duration |

**Related commits that don't change the decision**
- `4474af25` (2025-06-10) only adds log lines for the outcome of each processed instance.
- `d2675cf4` (2025-07-03) masks sensitive raw fields before processing.

----- next turn -----

The culprit is `917a0b7b` (2025-08-14), "share the lookback window computation". The fix is in, with a regression test. I ran only `tests/signal`: 33 pass and 1 is skipped.

**Cause.** Before that commit, a filter's window was read as minutes (`timedelta(minutes=f.window)`). The UI's field is "Window (minutes)" with choices 5, 10, 15, 20 and 30, and existing filters store minutes. The commit routed the value through `_window_start(seconds)` and added a comment saying it was stored in seconds. That comment was wrong. Your filter's 30 therefore became 30 seconds, and two instances ten minutes apart fell outside it.

The same commit also changed the default window for signals with no filters. It computed that window as minutes × 60 and passed it to a function that took seconds, so the default stayed at 45 minutes and was not affected.

**Fix.**
- In `src/dispatch/signal/service.py`, `_window_start` now takes minutes. The no-filter default passes `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` directly, and the comment on the per-filter window now says minutes.
- Stored values already mean minutes, so no migration is needed and existing filters keep working without edits.
- In `src/dispatch/signal/models.py`, the column default was 3600 with a comment saying seconds, which would now mean 60 hours. I changed it to 60 minutes. The API schema default was 600, which I changed to 10, matching the old "10 minutes" reading. Neither default affects existing rows.

**Test.** `test_filter_actions_deduplicate_window_is_in_minutes` in `tests/signal/test_signal_service.py` mirrors your case. A filter has a window of 30, and an earlier instance with a case sits 10 minutes back on the same entity. The new instance must be deduplicated into that case. The test fails with the signal source changes stashed.

The existing tests didn't catch this because they used a 5-minute window with instances created at the same moment.

Other things to know:
- Instances already split into separate cases since the 2025-08-14 deploy are not merged. Nothing in this fix revisits them.
- The `filter_signal` docstring still says "1-hour window" for the default, although it is 45 minutes.
- Nothing is committed.

----- next turn -----

The cause is `086dc910` (2025-08-07), "simplify snooze filter checks". It was labelled a refactor but changed behaviour. In `filter_snooze`, an expired snooze filter used to `continue` to the next filter. The commit changed that to `break`, which ends the whole loop. Your "Okta: Impossible travel" signal has the expired filter ahead of the valid one, so the loop stopped at the expired one and never checked the valid one. New instances for that user then fell through to deduplication and opened cases.

**Fix.** In `src/dispatch/signal/service.py`, the expired-filter branch is back to `continue`.

**Test.** `test_filter_actions_snooze_expired_filter_does_not_hide_active_one` in `tests/signal/test_signal_service.py` gives one signal two snooze filters on the same entity. The first expired 7 days ago and the second is valid for 30 more days. The instance must end up snoozed. It fails with the `service.py` changes stashed and passes with the fix. The signal tests now show 34 passed, 1 skipped.

When I stashed `service.py` to check the test fails without the fix, it also reverted the earlier window-in-minutes fix. That doesn't affect this test, because it doesn't involve a dedup window.

The same commit also removed the "has no mode" and "has no action" warnings. That only affects logging, so I left it. Nothing is committed.

----- next turn -----

Two investigations today: the weekly reminders that stopped in August, and the signal snooze and deduplication bugs. Everything below is fixed in the working tree with tests, and nothing is committed.

**1. Weekly reminders stopped (long-running triage and stable cases)**
- `c509d45e` (2025-08-12), "share the weekly reminder check", moved the Monday check into `_is_reminder_day()`. It compared `date.isoweekday()`, which runs 1–7 with Monday as 1, against `calendar.MONDAY`, which is 0. The check was never true, so the weekly jobs silently never sent anything. The daily triage reminders don't use this check, which is why they kept arriving.
- It shipped in image `main-81d8ae42` (started 2025-08-13 16:40 UTC in both the API and scheduler logs). The previous image was `main-b05613b5`. The first Monday after that deploy was 2025-08-18.
- Fix: the check now uses `weekday()`, which matches `calendar.MONDAY`. A parametrized test covers every day of a week.
- Nightly `TypeError` in the close reminder: the job subtracted `case.triage_at`, which is only set when a case goes through the triage transition. Other cases have it NULL. It now counts from `triage_at or created_at`, and a test covers that. `case_stable_reminder` still skips cases with no `stable_at`. I can add the same fallback if you want it.

**2. Signal snooze and deduplication**
- Four commits since 2025-05-22 changed the decision: `a348bbd2` (canary signals are never deduplicated and are ignored as match targets), `7a9fe810` (default window made configurable, 60 minutes down to 45), `086dc910` and `917a0b7b`.
- `917a0b7b` (2025-08-14) read a filter's window as seconds, but the UI and stored data are minutes. A 30 became 30 seconds. It is fixed back to minutes, and the column and schema defaults are now in minutes. A regression test covers it.
- `086dc910` (2025-08-07) changed an expired snooze from `continue` to `break`, so a valid snooze listed after an expired one was never evaluated. It is fixed, with a regression test.
- Instances that were already split into separate cases or not snoozed during the bad periods are not repaired.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e
DEPLOYED_IMAGE: registry.example.com/dispatch:main-81d8ae42
FIRST_MISSED: 2025-08-18
MISSING_FIELD: triage_at
DEDUP_WINDOW_BUG: 917a0b7b
SNOOZE_BUG: 086dc910
CANARY: a348bbd2
DEFAULT_WINDOW: 45 minutes
DEFAULT_WINDOW_SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES