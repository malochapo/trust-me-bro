**Root cause:** commit `c509d45e`, "refactor(case): share the weekly reminder check" (Jordan Lee, 2025-08-12), broke the Monday check in `src/dispatch/case/scheduled.py`.

- The refactor replaced `date.today().isoweekday() == 1` with a new helper, `_is_reminder_day()`. The helper returns `date.today().isoweekday() == calendar.MONDAY`.
- `calendar.MONDAY` is `0` (Monday is the first day in `calendar`'s 0–6 numbering), but `isoweekday()` returns 1–7. The comparison can never be true.
- `case_close_reminder` (long-running triage cases) and `case_stable_reminder` (stable cases) both gate on `q >= 1 and _is_reminder_day()`, so neither ever sends. The helper fails silently, so there are no new errors and no log noise.
- The daily triage reminder (`case_triage_reminder`) doesn't use the helper, which is why it still arrives. No settings were involved.
- The correct fix would be `isoweekday() == 1` or `date.today().weekday() == calendar.MONDAY`. I haven't changed any code.

**Log evidence:**

| Monday | Case close reminders sent |
|---|---|
| 07-28 | 4 |
| 08-04 | 6 |
| 08-11 | 5 |
| 08-18 | 0 |

- 08-11 is the last Monday with sends. 08-18 is the first Monday after the deploy, and nothing went out.
- The `unsupported operand type(s) for -: 'datetime' and 'NoneType'` errors appear daily from 07-28, before the refactor. They come from cases with no `triage_at` or `stable_at`, and are a separate, pre-existing issue, not the cause. After the deploy only the `case_close_reminder` error remains, because `32fa810f` (a `stable_at` None guard) shipped in the same deploy.

**The deploy:** the production image `registry.example.com/dispatch:main-81d8ae42` went out on **2025-08-13 at ~16:40 UTC**.

- Both the scheduler pod (`scheduler-mhtsgqwwx-q5q2n`) and the web pod (`web-5dkmr9s9s-xxktx`) started that image, per the kubelet "Started container" lines.
- It replaced `main-b05613b5`, which had run since 2025-07-30 and did not contain the refactor.
- `81d8ae42` is "fix(case): exclude resolved_by in update (#6183)". It is the tip of the range that first includes `c509d45e`, along with about 27 other commits.
- The log shows the image tag but doesn't name the pipeline run, so I can't say who triggered the deploy.

The 08-11 Monday reminders ran on the old image, which is why the break only showed up on 08-18, a few days after the deploy.

----- next turn -----

The Monday reminders for long-running triage and stable cases should send again once this change is deployed.

**Fix:** in `src/dispatch/case/scheduled.py`, `_is_reminder_day()` now compares `date.today().weekday()` to `calendar.MONDAY`. Both use 0–6 numbering, so the check is true on Mondays. Before, it compared `isoweekday()` (1–7) to `calendar.MONDAY` (0), which could never match.

**Regression test:** `tests/case/test_case_scheduled.py` adds 12 cases:
- **`_is_reminder_day()`:** two Mondays (2025-08-11 and 2025-08-18) must be true, and the other five weekdays through Sunday must be false.
- **The `case-close-reminder` and `case-stable-reminder` tasks:** each is run on a Monday and on a Tuesday against a 10-day-old case. The reminder must be sent on Monday and not on Tuesday.

The scheduled functions are wrapped by the scheduler decorators, so the test pulls the original function out of `scheduler.registered_tasks`.

**Verification:** with the fix, all 12 tests pass, and so does the rest of `tests/case` (27 tests in total). With the fix reverted, 4 of the 12 fail: both Monday `_is_reminder_day` cases and both Monday task cases. These are the Monday checks that would have caught the bug.

Nothing is committed, and this still needs to be deployed to production before reminders resume. I didn't touch the separate `None` `triage_at`/`stable_at` errors, which the close-reminder task still logs daily.

----- next turn -----

The daily `TypeError` in the case close reminder job is fixed. Cases with no `triage_at` now count from `created_at`, so they get their weekly reminder. The 29 tests in `tests/case` pass. With the source changes reverted, 5 of the 14 scheduled-job tests fail, including the new `created_at` test.

**Cause:** `case_close_reminder` loads every case in `triage` status and computes `datetime.utcnow() - case.triage_at`. `triage_at` is only set by `case_triage_status_flow`, which runs on a `new → triage` or `closed → triage` transition.

I did not look at the data, so I can't say which route produced the affected cases. Two code paths can leave a triage case without `triage_at`:
- **Created directly in triage:** `case/service.py` `create` takes `status` from the input and never sets `triage_at`.
- **Other transitions:** any other `X → triage` transition only hits the "Unexpected previous state" warning branch in the dispatcher and doesn't set it.

Either way, the subtraction raises `TypeError`, and the per-case `try/except` logs it. That's why the error appeared every evening. It also means those cases never got the weekly reminder, and this was already happening before the Monday bug.

**Fix:** in `src/dispatch/case/scheduled.py`, the job now uses `case.triage_at or case.created_at`. `created_at` is already loaded by `get_all_by_status`.

**Tests** (added to `tests/case/test_case_scheduled.py`):
- A 10-day-old triage case with no `triage_at` sends the reminder on a Monday and logs no exception.
- A 2-day-old one with no `triage_at` doesn't send.

**Not changed:**
- `case_stable_reminder` still skips cases with no `stable_at`, which is the behaviour from `32fa810f`. You only asked about the close reminder, so I left it. I can give it the same `created_at` fallback if you want.
- Nothing sets `triage_at` for cases created directly in triage. The job now tolerates that, but fixing it at the source would be a separate change.
- Nothing is committed.

----- next turn -----



----- next turn -----

Five commits since 2025-05-22 changed this logic, and one of them looks like a regression. Today the code reads a filter's `window` as seconds, but the UI still sends minutes. The decision logic is in `src/dispatch/signal/service.py`: `filter_snooze`, `filter_dedup` and the new `_window_start`.

**Commits**

1. **`a348bbd2`** (2025-05-29, "don't dedup on canary signals")
   - A canary signal instance skips deduplication entirely.
   - Canary instances are also ignored as dedup matches, both for the default no-filter path and for filter-based dedup.
   - This commit changes no time window.

2. **`7a9fe810`** (2025-06-19, configurable default window)
   - The default window for signals that have no filters was hard-coded at `timedelta(hours=1)`.
   - It now comes from the new `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` setting in `config.py`, whose default is **45 minutes**.
   - So any deployment that doesn't set the env var went from 1 hour to 45 minutes.

3. **`086dc910`** (2025-08-07, "simplify snooze filter checks")
   - It collapsed the mode and action checks in `filter_snooze` into one condition and dropped the "no mode" and "no action" warnings.
   - It also changed the expired-snooze case from `continue` to `break`. An expired snooze filter now stops the loop, so any later snooze filters on that signal are no longer checked.
   - That `continue` → `break` change is probably unintended for a refactor.
   - There is no time window here except the filter's own `expiration` date.

4. **`917a0b7b`** (2025-08-14, "share the lookback window computation")
   - It added `_window_start(seconds)`, which returns now minus that many seconds. Both dedup paths use it.
   - The default path is unchanged in effect: `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES * 60` seconds, so **45 minutes**.
   - The filter-based path changed from `timedelta(minutes=f.window)` to `_window_start(f.window)`, which treats `f.window` as **seconds**.
   - The model column is documented as seconds with a default of 3600, and the Pydantic default is 600.
   - The UI create dialog (`SignalFilterCreateDialog.vue`) labels the field "Window (minutes)" and offers 5, 10, 15, 20 and 30.
   - I didn't trace how the UI value reaches the API.
   - If the UI really sends those minute values as-is, a filter set to 30 now dedups over 30 seconds instead of 30 minutes. A filter's `window` value is also read as seconds, not minutes, for filters created before this commit (that's the reading I'd check).
   - Verify what unit is actually stored and sent before trusting this.

5. **`4474af25`** (2025-06-10)
   - It only adds log lines in `signal/flows.py` for the filter action and case ID. It changes no behaviour.

**Windows as the code applies them today**
- **Default, no filters:** 45 minutes, configurable through `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`.
- **Deduplicate filter:** `f.window` seconds, with a model default of 3600 s and a Pydantic default of 600 s.
- **Snooze filter:** no lookback window, only the filter's `expiration` timestamp.

The two items to check are the `window` unit mismatch in `917a0b7b` and the `break` change in `086dc910`. No code was changed.

----- next turn -----

**Cause:** `917a0b7b` (2025-08-14, "share the lookback window computation"). Before it, the filter path used `timedelta(minutes=f.window)`. That commit made it `_window_start(f.window)`, which subtracts seconds, and added a comment saying the value is "stored in seconds". The UI field is "Window (minutes)" (options 5, 10, 15, 20, 30), and the old code treated it as minutes. So your filter set to 30 has been deduplicating over 30 seconds instead of 30 minutes. Two instances ten minutes apart fall outside that, so each opened its own case. The other commits I listed don't touch this path.

**Fix:**
- In `src/dispatch/signal/service.py`, the filter path now calls `_window_start(f.window * 60)`. Existing filters keep their stored values (30 still means 30 minutes), so none need editing.
- In `src/dispatch/signal/models.py`, I corrected the `window` column comment from "seconds" to "minutes".

**Test:** `test_filter_actions_deduplicate_window_is_in_minutes` in `tests/signal/test_signal_service.py`. It builds a dedup filter with `window=30` and an earlier instance for the same entity ten minutes old, and expects the new instance to be deduplicated.
- With the fix, `tests/signal` gives 33 passed, 1 skipped.
- With the `src` changes stashed, the new test fails and the rest pass.

**Not changed:**
- The column default is `60 * 60` and the Pydantic default is `600`. Read as minutes, those are 60 hours and 10 hours. They are probably leftovers from when this was thought of as seconds. Filters created through the UI always send an explicit value, so I left them alone. Say if you want them changed.
- I haven't touched the `continue` → `break` change in `086dc910`.
- Instances that were already split into separate cases between 2025-08-14 and the deploy of this fix are not merged back.
- Nothing is committed. The fix needs to be deployed.

----- next turn -----

This is the `continue` → `break` change I flagged earlier in `086dc910` (2025-08-07, "simplify snooze filter checks"). Same batch of changes, a different commit from the dedup-window bug.

**Cause:** `filter_snooze` loops over the signal's filters. For an expired filter the original code did `continue`, which moves on to the next filter. That commit changed it to `break`, which ends the loop. If the expired "Okta: Impossible travel" filter is checked before the valid one, the valid snooze filter is never evaluated. New instances for that user then aren't snoozed.

**Fix:** in `src/dispatch/signal/service.py`, the expired-filter branch is back to `continue`, with a comment saying an expired filter must not hide later valid ones.

**Test:** `test_filter_actions_snooze_expired_filter_does_not_hide_valid_one` in `tests/signal/test_signal_service.py`. It gives a signal two snooze filters for the same entity, expired 7 days ago listed first and valid for 30 more days listed second. It expects the instance to be snoozed.
- With the fix, `tests/signal` gives 34 passed, 1 skipped.
- With the `src` changes stashed, the new test fails, along with the dedup-window test from the previous fix, and nothing else does.

Nothing is committed. This needs deploying along with the earlier fixes.

----- next turn -----

## Recap

**1. Weekly Monday close reminders stopped (case reminders)**
- **Cause:** `_is_reminder_day()` in `src/dispatch/case/scheduled.py` compared `date.isoweekday()` (Monday is 1 and Sunday is 7) with `calendar.MONDAY` (which is 0). The check was never true, so the weekly triage and stable reminders stopped. The daily triage reminders don't use that check, so they kept arriving.
- **Introduced by:** `c509d45e`. It shipped in image `main-81d8ae42` on 2025-08-13 at about 16:40 UTC. That was a Wednesday, so the first Monday affected was 2025-08-18.
- **Fix:** the check now uses `date.today().weekday() == calendar.MONDAY`. Regression tests are in `tests/case/test_case_scheduled.py`.

**2. Evening `TypeError` in the case close reminder job**
- **Cause:** the job computes `datetime.utcnow() - case.triage_at`, but `triage_at` is only set by the status-transition flow into triage. Cases created directly in triage, or that reached it by another transition, have `triage_at` as None. The per-case `try/except` logged the error each evening, and those cases never got a reminder.
- **Fix:** the job now counts from `case.triage_at or case.created_at`. Tests cover a 10-day-old case with no `triage_at` (reminder sent) and a 2-day-old one (not sent).
- **Left alone:** `case_stable_reminder` still skips cases with no `stable_at`.

**3. Signal snooze and deduplication changes since 2025-05-22**
- `a348bbd2` made canary signal instances skip deduplication and stopped them from matching as duplicates.
- `7a9fe810` made the default dedup window configurable. It was 1 hour and is now 45 minutes unless the setting is overridden.
- `086dc910` changed `continue` to `break` for an expired snooze filter. A valid snooze filter listed after an expired one was then never checked. I fixed it by restoring `continue` and added a regression test.
- `917a0b7b` made the filter window count seconds, while the UI field "Window (minutes)" still sends minutes. A window of 30 became 30 seconds, which is why the two GuardDuty instances ten minutes apart opened two cases. I fixed it with `f.window * 60`, so existing filters work without being edited, and added a regression test.
- `4474af25` only added log lines.

Nothing is committed. All three fixes need to be deployed.

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