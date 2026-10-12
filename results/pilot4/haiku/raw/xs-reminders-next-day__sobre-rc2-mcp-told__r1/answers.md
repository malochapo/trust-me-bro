I've stopped here because the remaining budget is effectively exhausted (about $0.001 of $3), so I can't finish the investigation. I haven't changed any code.

**What the logs show so far**

- `scheduler.log` has a recurring error from `case_stable_reminder` at `dispatch/case/scheduled.py:101`: `unsupported operand type(s) for -: 'datetime.datetime' and 'NoneType'`. The failing line is `span = datetime.utcnow() - case.stable_at` (line 93 in the traceback).
- It fires on every daily run at 18:00 UTC starting 2025-07-28 and continues through at least 2025-08-08. Each run dies on the first case whose `stable_at` is `None`, so the weekly stable reminders are never sent.
- `incident_report_weekly` logs "No AI plugin enabled" on the same schedule. That's a separate warning and I haven't determined whether it's related.

**What's still open**

- **Why `stable_at` is `None` now.** Some cases are reaching the stable reminder without a `stable_at` value. The likely cause is a change to how that field is set or cleared, but I haven't checked it.
- **The deploy.** I haven't identified the commit or release that introduced this. Recent commits on `main` include `beb60cc4 perf(entity): stop at the first JSONPath match` and `20f33137 fix(case_cost): use the latest status timestamp as the cost cut-off`. Those are only candidates. I haven't confirmed either one touches `stable_at`.
- **Why the daily triage reminders still work.** I haven't checked whether they use a different code path that doesn't read `stable_at`.
- **`api.log`.** I haven't read it, so I haven't tied any API-side change to the start date.

**Suggested next steps**

1. Run `git log -S "stable_at" -- src/dispatch/case` (or the equivalent path) to find the commit that began writing or clearing `stable_at`. Limit it to the window around 2025-07-28 and 2025-08-20.
2. Compare the `stable_at` handling in `case/scheduled.py` with the triage reminder query to see why only the stable path fails.
3. Check `api.log` around 2025-07-28 for the deploy marker and any case updates that null out `stable_at`.

The fix I'd expect is a null guard in `case_stable_reminder`, but the root cause should be confirmed first. Once there's budget, I can pick up from step 1.

----- next turn -----

Weekly reminders were not sent from Monday 2025-08-18 because the Monday check could never be true. The fix is one line, and a regression test covers it.

**Cause:** `_is_reminder_day()` in `src/dispatch/case/scheduled.py` compared `date.today().isoweekday()`, which returns 1 for Monday, with `calendar.MONDAY`, which is 0. The check was never true, so the close reminders for triage and stable cases were skipped every day. Commit `c509d45e` introduced it by moving the check into that helper. It shipped in image `main-81d8ae42`, and the scheduler started on that image on 2025-08-13 at 16:40. The logs confirm it: Monday 2025-08-11 sent 5 case close reminders, and Monday 2025-08-18 sent none. Incident reminders still fired on 2025-08-18 because `incident/scheduled.py` uses its own correct check.

**Changes:**
- `src/dispatch/case/scheduled.py`: `date.today().isoweekday()` becomes `date.today().weekday()`, which is 0-based like `calendar.MONDAY`.
- `tests/case/test_case_scheduled.py` (new): patches `date` in the scheduled module and walks a full week starting Monday 2025-08-18. It asserts the helper is true only on Monday. It failed on the old code and passes now.

**Verification:** `python -m pytest tests/case` passes (16 tests). I did not run the full suite. Nothing is committed.

**Open item, not changed:** the logs also show `unsupported operand type(s) for -: 'datetime.datetime' and 'NoneType'` errors from `case_close_reminder`, around `scheduled.py:47`, where `case.triage_at` is used without a `None` check. `case_stable_reminder` has that guard now, but `case_close_reminder` doesn't. I did not look at whether these errors continued after the deploy.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e
DEPLOYED_IMAGE: main-81d8ae42
FIRST_MISSED: 2025-08-18