**Root cause:** commit `c509d45e` ("refactor(case): share the weekly reminder check", Jordan Lee, 2025-08-12) moved the Monday test into `_is_reminder_day()` and compared the wrong weekday scheme:

```python
# src/dispatch/case/scheduled.py:31-33
def _is_reminder_day() -> bool:
    """Reminders about long-running cases go out once a week, on Mondays."""
    return date.today().isoweekday() == calendar.MONDAY
```

`isoweekday()` numbers Monday as 1, but `calendar.MONDAY` is 0 (Monday-based `weekday()` numbering). The old code compared `isoweekday()` to `1`, which was correct. After the refactor the check is never true, so `q >= 1 and _is_reminder_day()` never passes and neither weekly reminder is sent. I confirmed this with Python: `calendar.MONDAY == 0`, and 2025-08-18 has `isoweekday() == 1`, so the comparison is `False`.

**Deploy that shipped it:** image `registry.example.com/dispatch:main-81d8ae42`, started 2025-08-13 16:40 (`api.log`). That is the `main` HEAD `81d8ae42` (fix(case): exclude resolved_by in update, #6183), and `c509d45e` is an ancestor of it. The scheduler pod also rotated to `scheduler-mhtsgqwwx-q5q2n` on 08-13, consistent with this deploy.

**Log evidence (`scheduler.log`):**
- "Case close reminder sent" lines: 4 on 07-28, 6 on 08-04, 5 on 08-11 (Mondays).
- Monday 2025-08-18 at 18:00: no close or stable reminder sends, and no errors from the weekly path. The daily `case-triage-reminder` still ran and sent ("Case triage reminder sent to …"), which matches what you saw.

**Scope:** `case_close_reminder` (triage cases) and `case_stable_reminder` (stable cases) both use `_is_reminder_day()`, so both weekly reminders stopped. `case_triage_reminder` does not use it and is unaffected.

**Ruled out:**
- The `NoneType` errors on `stable_at`/`triage_at` in the logs are a separate issue. They were the bug fixed by `32fa810f` on 08-11, and they were caught per case, so they did not stop the Monday sends. The 08-11 sends happened after that and before the deploy.
- The `scheduler` pod restarts and the 08-13 `api` deploy aren't the cause on their own. The timing lines up because the refactor shipped in that image.

**Side finding:** `case_close_reminder` still logs a `TypeError` on `case.triage_at` being `None` for some triage cases (e.g. 08-18 18:00:00.192, `scheduled.py:47`). Each one is caught, so other cases still process, but it's an error every day and worth a look.

**Suggested fix (not applied):** use the 0-based weekday to match `calendar.MONDAY`, i.e. `date.today().weekday() == calendar.MONDAY`, or go back to `isoweekday() == 1`. Also add a test that pins Monday to the 0-based value so the mismatch can't recur. Once fixed and deployed, the next Monday run should resume the reminders.

No code was changed.

----- next turn -----

The weekly reminders are fixed and there is a regression test for it. Nothing is committed.

**The fix:** in `src/dispatch/case/scheduled.py`, `_is_reminder_day()` now uses `date.today().weekday()` instead of `isoweekday()`. `calendar.MONDAY` is 0, so it has to be compared against the 0-based `weekday()`. The change is one line.

**The regression test:** `tests/case/test_case_scheduled.py` pins "today" to each day of a single week and checks that `_is_reminder_day()` is true only on Monday.
- Against the fixed code: 7/7 pass.
- Against the original `isoweekday()` line: the Monday case fails, which is the bug you hit.

**Test runs (PostgreSQL was up):**
- `python -m pytest tests/case/test_case_scheduled.py`: 7 passed.
- `python -m pytest tests/case`: 22 passed.

I didn't run the full suite, only the case tests. Nothing else in the diff touches the reminder path, so I'd expect the rest to be unaffected, but I haven't checked that.

I didn't commit or push. The side finding from before is also still open: `case_close_reminder` logs a `TypeError` for triage cases with a `None` `triage_at` each day. It's caught per case, so I left it alone.

----- next turn -----

The close-reminder TypeError is fixed. Cases with no `triage_at` now count from `created_at`, and the new tests cover it. I didn't commit anything.

**What causes the TypeError:** `triage_at` is only written by `case_triage_status_flow` (`src/dispatch/case/flows.py:592`). Two paths can move a case to Triage without it:
- **Most likely:** `reopen_button_click` (`src/dispatch/plugins/dispatch_slack/case/interactive.py:1427`) assigns `case.status = CaseStatus.triage` directly and never runs the transition flow. A case closed from New and then reopened never gets a `triage_at`.
- **Also possible:** the catch-all "Any → Triage" branch in `case_status_transition_flow_dispatcher` (`flows.py:766`) logs a warning and sets nothing. That covers transitions such as Escalated or Stable → Triage.

The logs don't carry case IDs, so I couldn't confirm which of these produced the cases in production. I didn't check the database either. The fix works for both.

**The fix** (`src/dispatch/case/scheduled.py`, in `case_close_reminder`):
```python
span = datetime.utcnow() - (case.triage_at or case.created_at)
```
`created_at` is set by a column default, so it's always present. When `triage_at` is set, it is still used.

**Tests** (`tests/case/test_case_scheduled.py`), run against the real Postgres database:
- A triage case with no `triage_at`, created 8 days ago, gets the reminder.
- A triage case with no `triage_at`, created 2 days ago, does not.
- A case with a recent `triage_at` and an old `created_at` does not get one, so `triage_at` still takes priority.

The tests stub the Monday check and the send call, and run the job body through the scheduler registry. The positive test fails when the fallback is reverted, so it does catch the bug.

**Results:** `python -m pytest tests/case` passes (25 tests). The Monday-day tests from the previous fix are also in that run.

**Two things to know:**
- `CaseFactory` pins `status` to `"New"` through its `Params` block, so the new tests set `Triage` after creating the case. I didn't change the factory, since it's shared by other tests.
- `case_stable_reminder` still skips stable cases that have no `stable_at`, which is the behaviour from the earlier guard. I left that alone because you only asked about the triage job. If you want stable cases to fall back to `created_at` too, that's a one-line change.

I didn't change the reopen path, so reopened cases will still have no `triage_at`. If you want that fixed at the source, it's a small change to route the reopen through `case_status_transition_flow_dispatcher`.

----- next turn -----



----- next turn -----

Four commits since 2025-05-22 changed snooze or deduplication. Nothing has been changed in the code.

**Commits (oldest first)**

1. **`a348bbd2`** (2025-05-29, Will Sheldon): *don't dedup on canary signals.* Canary instances skip deduplication entirely, and canary instances are excluded from the instances that deduplication matches against. No window change. In deployed HEAD `81d8ae42`.

2. **`7a9fe810`** (2025-06-19, Jordan Lee): *make the default dedup window configurable.* The window for signals with no dedup filter moved from a hard-coded 1 hour to `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`, which defaults to **45 minutes**. This is a shorter default than before. In `81d8ae42`.
   - The new setting sits between `DISPATCH_UI_URL` and `DISPATCH_ENCRYPTION_KEY` in `src/dispatch/config.py`, so the encryption key now falls under the "# signals" comment.
   - The `filter_signal` docstring still says "1-hour window".

3. **`086dc910`** (2025-08-07, Sam Ortega): *simplify snooze filter checks.* In `filter_snooze`, an expired snooze filter now does `break` instead of `continue`, so any later filters on that signal are skipped. The missing-mode and missing-action warnings were also removed. In `81d8ae42`.

4. **`917a0b7b`** (2025-08-14, Jordan Lee): *share the lookback window computation.* A per-filter dedup window used to be `timedelta(minutes=f.window)`. It is now `f.window` taken as **seconds**. This is a 60× change in how long existing dedup filters look back. It is on `main` but **not in deployed HEAD `81d8ae42`**, so it hasn't shipped yet, unless it's deployed separately. The commit message doesn't mention the behaviour change.

**Windows as the code applies them today**

- **Snooze:** no lookback window. A snooze filter is active until its `expiration`. A filter with no expiration is skipped with a warning. The expression is optional. If it's empty, the snooze applies to every instance of the signal.
- **Dedup, signal with no dedup filters:** the window is `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` × 60 seconds, so **2700 s (45 min)** by default. It only matches instances that already have a case.
- **Dedup, per filter:** `SignalFilter.window` is in **seconds**. The column default is **3600 s (1 h)**, and the API schema default is **600 s (10 min)**. There is no minimum. The tests in `tests/signal/test_signal_service.py` use `window=5`, which is 5 seconds.

**Things to decide**

- The unit change in `917a0b7b` affects existing filters. Before it, a stored `window` of 600 meant 10 hours, and the schema default of 600 now means 10 minutes. Stored values may need converting, or the change may need to be reverted until that's done.
- The snooze `break` in `086dc910` means signal filters after an expired snooze are no longer checked. That may be intended, but nothing in the commit says so.

----- next turn -----

The 30-minute window now groups those two instances. The cause was `917a0b7b` (2025-08-14, "share the lookback window computation"). It changed a deduplication filter's window from minutes to seconds. The UI says "Window (minutes)", so a 30 became 30 seconds, and two instances ten minutes apart fell outside it. The other commits in the list don't touch the window.

**Fix** (`src/dispatch/signal/service.py`):
- `_window_start` now takes minutes. The per-filter window passes `f.window` straight through, and the signal default passes `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` without the old `* 60`.
- The comment in `src/dispatch/signal/models.py` now says the window is in minutes, as entered in the UI.

Existing filters need no edits or migration. Their stored values were always entered as minutes, so they'll now mean what the UI shows.

**Tests** (`tests/signal/test_signal_service.py`): two regression tests use a filter with `window=30`.
- An instance created 10 minutes earlier is deduplicated. This one fails on the old code and passes now.
- An instance created 40 minutes earlier is not deduplicated, which pins the window's upper bound.

**Results:** `python -m pytest tests/signal` passes (34 passed, 1 skipped). I did not run the full suite.

**Left unchanged, for you to decide:**
- The model default of `window` is 3600 and the API schema default is 600. Under minutes, those mean 60 hours and 10 hours. They only apply when a filter is created without a window, and I kept them as-is to avoid changing new-filter behaviour. If the intent was one hour, the default should be 60.
- The `filter_signal` docstring still says "1-hour window" for the default path. That's still accurate for the 45-minute default only in the sense that it's now configurable, so I didn't touch it.
- The default dedup window is still `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`, which defaults to 45. That's the value from `7a9fe810`, not something I changed.

Nothing is committed. Also, `917a0b7b` is on `main` but not in deployed HEAD `81d8ae42`, so this fix matters only if that commit has been or will be deployed.

----- next turn -----

The cause was `086dc910` (2025-08-07, "simplify snooze filter checks"). It changed the expired-filter branch in `filter_snooze` from `continue` to `break`. The loop stops at the first expired snooze filter, so any filters after it are never checked. For the "Okta: Impossible travel" signal, the expired filter came first, so the valid one was never reached.

**Fix** (`src/dispatch/signal/service.py`): the expired-filter branch uses `continue` again. The other checks stay as they were.

**Regression test** (`tests/signal/test_signal_service.py`): `test_filter_actions_snooze_expired_then_active` puts an expired snooze filter ahead of a valid one for the same entity, then asserts the instance is snoozed. It fails on the `break` code and passes with the fix.

**Results:** `python -m pytest tests/signal` passes (35 passed, 1 skipped). I did not run the full suite.

Nothing is committed. `086dc910` is in deployed HEAD `81d8ae42`, so this bug is live.

----- next turn -----

Here is the recap for both investigations. The changes are in the working tree and nothing is committed.

**Monday reminders and the evening TypeError**
- Weekly Monday reminders stopped after the 2025-08-13 deploy. `_is_reminder_day()` in `src/dispatch/case/scheduled.py` compared `date.today().isoweekday()` (Monday = 1) with `calendar.MONDAY` (Monday = 0). The check was never true, so no Monday reminders went out. The bad line came in with `c509d45e` (2025-08-12, "share the weekly reminder check"). The fix changes it to `date.today().weekday()`. The logs show close reminders on 2025-08-11 and none on 2025-08-18.
- The deploy was image `main-81d8ae42`. It started on the web and scheduler pods on 2025-08-13.
- The evening TypeError comes from `case_close_reminder`. `case.triage_at` is `None` for some triage cases, and subtracting it from `datetime.utcnow()` raised the error. The fix counts from `created_at` when `triage_at` is missing. Three tests cover it. The root cause is not confirmed: the likely source is the Slack reopen handler (`reopen_button_click`), which sets status to triage without setting `triage_at`. The logs don't name the case, so the source has not been verified. That handler is unchanged.
- Tests: `python -m pytest tests/case` passes, 25 tests.

**Snooze and deduplication**
- A deduplication window that was entered in minutes in the UI was treated as seconds after `917a0b7b` (2025-08-14). A 30-minute window became 30 seconds, so two instances ten minutes apart opened two cases. The fix reads windows in minutes again, so existing filters work without edits. Two regression tests cover it.
- The snooze bug came from `086dc910` (2025-08-07). An expired snooze filter now stopped the loop with `break`, so valid filters later in the list were never checked. The fix changes it back to `continue`. One regression test covers it.
- The canary behaviour changed in `a348bbd2` (2025-05-29): canary instances skip deduplication and are excluded from matching. No tests were added for that change in this session.
- Tests: `python -m pytest tests/signal` passes, 35 tests, 1 skipped. The full suite was not run.
- The default grouping window for signals with no filter is 45 minutes. It is set by `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`.

**Open items**
- Per-filter default windows: the model default is 3600 and the schema default is 600, now read as minutes. That is 60 hours and 10 hours. Decide whether these should be 60 and 10.
- `917a0b7b` is on `main` but not in deployed `81d8ae42`. `086dc910` is in the deployed image, so the snooze bug is live.
- The missing-`triage_at` source is unconfirmed, and the reopen path is still open.
- Nothing is committed.

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