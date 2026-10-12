I'm stopping here because the budget is almost used up ($0.001 of $3 left). I have a partial answer, but I have not confirmed the root cause or the deploy.

**What the logs show so far**

- `scheduler.log` has an error on every daily run of the stable-case reminder from 2025-07-28 onward, starting at 18:00 UTC. The error is `unsupported operand type(s) for -: 'datetime.datetime' and 'NoneType'` at `dispatch/case/scheduled.py:101`, inside `case_stable_reminder`. The failing line is `span = datetime.utcnow() - case.stable_at` (line 93 in the traceback), so `case.stable_at` is `None` for at least some cases.
- The weekly incident report also logs `Incident weekly reports not sent. No AI plugin enabled.` on Mondays (for example 2025-07-28 and 2025-08-04). That is a separate warning and does not explain the missing case reminders.
- I did not check whether the weekly long-running and stable reminders use the same code path. The traceback points only at the daily stable reminder.

**What I have not established**

- **Root cause:** the `None` for `stable_at` is the likely cause, but I have not found where `stable_at` stops being set. The error is also in the logs from 07-28, earlier than the mid-August start you described, so the timing does not match yet.
- **Deploy:** I have not identified which commit shipped the change. I only saw the recent commit list in the git status, and I did not check git history for `case/scheduled.py` or `stable_at`.
- **API log:** I have not checked `api.log` at all.

**Suggested next steps**

1. Check `git log -p -- src/dispatch/case/scheduled.py` and `git log -S stable_at` in the repo to find the commit that changed how `stable_at` is set or read.
2. Check the API log around mid-August for the code path that writes `stable_at`, and whether cases lose that value after an update.
3. Compare the weekly reminder query with the daily one. The daily triage reminder still works, so the weekly path may filter on `stable_at` or on a related field.

I have not changed any code. Given the budget, I'd recommend continuing in a new session with more budget, and I can pick up from the git history step.

----- next turn -----

I saved the findings and the next steps to the sobre session, so tomorrow's session can start from `sobre_session` with `action="load"`.

**Saved finding:** `case_stable_reminder` in `dispatch/case/scheduled.py` fails on every daily run from 2025-07-28 with `datetime - NoneType`, at `span = datetime.utcnow() - case.stable_at`. So `stable_at` is `None` for some cases. The "No AI plugin enabled" warning on Mondays is separate and doesn't explain the missing reminders.

**Saved decision:** no code changes yet. Tomorrow's steps are:
1. Run `git log -p` on `src/dispatch/case/scheduled.py` and `git log -S stable_at` to find the commit that changed how `stable_at` is set or read, which is the likely deploy.
2. Check `api.log` around mid-August for writes to `stable_at`.
3. Compare the weekly reminder query with the daily one.
4. Reconcile the 07-28 error onset with the mid-August report, since the dates don't match yet.

Still open: the root cause and the deploy are not confirmed, and `api.log` has not been read.

----- next turn -----

The weekly Monday reminders for long-running triage and stable cases are fixed, and a regression test covers the bug. I haven't committed anything.

**Cause:** Refactor `c509d45e` (2025-08-12, "share the weekly reminder check") moved the Monday check into `_is_reminder_day()`. It had been `date.today().isoweekday() == 1`. The refactor changed the right-hand side to `calendar.MONDAY`, which is `0` in Python's `calendar` module, while `isoweekday()` returns `1` for Monday. The condition never matched, so no weekly reminder has gone out since.

**Timeline from the logs:** The last close reminders were sent on Monday 2025-08-11, before the refactor shipped. The scheduler restarted on image `main-81d8ae42` on 2025-08-13, and that image contains `c509d45e`. The first Monday without reminders is 2025-08-18.

**Changes:**
- `src/dispatch/case/scheduled.py`: `_is_reminder_day()` now compares `date.today().weekday()` with `calendar.MONDAY`, so both sides use the same zero-based numbering.
- `tests/case/test_case_scheduled.py` (new): checks that the helper returns true only on Monday for each day of a week, and separately checks Monday 2025-08-18 with `calendar.MONDAY`. I confirmed the tests fail when the buggy line is restored and pass with the fix.

**Verification:** `python -m pytest tests/case` passes (23 tests). I didn't run the full suite.

**Not done:** The scheduler log also shows `case_stable_reminder` raising `TypeError` on cases with `stable_at = None`, with a traceback at `scheduled.py:93`. That's a separate issue. The `if case.stable_at:` guard should cover it, so it's worth a look, but I didn't investigate it further. Nothing committed.

I couldn't load an earlier sobre session to check yesterday's notes, so this comes from the logs and git history alone. I recorded the finding with `sobre_session`.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e97f4eeacf950450c142ee27da8fcda3f
DEPLOYED_IMAGE: main-81d8ae42
FIRST_MISSED: 2025-08-18