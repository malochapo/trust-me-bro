## Recap

**Weekly reminder outage.** Since mid-August, assignees didn't get the Monday reminders for long-running triage and stable cases. Daily triage reminders kept working.

- **Cause:** Commit `c509d45e` ("refactor(case): share the weekly reminder check") moved the Monday check into `_is_reminder_day()`. The refactor compared `date.today().isoweekday()` to `calendar.MONDAY`, which is `0` in Python. `isoweekday()` returns `1` for Monday, so the check was never true and no weekly reminders were sent.
- **Deploy:** Image `registry.example.com/dispatch:main-81d8ae42`, rolled out 2025-08-13 at 16:40Z. It contains `c509d45e`. The Monday before it, 2025-08-11, ran the old code and was fine.
- **Fix:** `_is_reminder_day()` compares to `1`. Covered by a regression test that fails on the buggy code.

**Evening TypeError.** The case close reminder logged `TypeError: unsupported operand type(s) for -: 'datetime.datetime' and 'NoneType'` every evening from 2025-07-28. Some triage cases had no `triage_at`. Moving a case from stable or escalated to triage does not set it, because the status dispatcher's catch-all `(_, triage)` branch skips the timestamp. I reproduced that in the test database. The logs don't name the affected case, so I couldn't confirm which transition happened in production.
- **Fix:** The close reminder counts from `triage_at`, falling back to `created_at`. Covered by tests, including one that fails without the fallback.
- **Not changed:** The catch-all branch still doesn't set `triage_at`. Fixing it changes what `triage_at` means for those transitions, so that's a call for the team.

**Tests:** The reminder test file passes (12 tests). The full suite has 8 failures in `tests/ai`, `tests/database`, and `tests/entity`. These are the same before and after my changes and look unrelated. One workflow test error from an earlier run did not recur.

Nothing is committed.

```
FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e97f4eeacf950450c142ee27da8fcda3f
DEPLOYED_IMAGE: main-81d8ae42
FIRST_MISSED: 2025-08-18
MISSING_FIELD: triage_at
```