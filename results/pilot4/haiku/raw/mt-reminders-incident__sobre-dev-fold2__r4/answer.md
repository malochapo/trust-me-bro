**Recap**

- **Weekday bug:** Commit `c509d45e` (2025-08-12, "refactor(case): share the weekly reminder check") replaced `date.today().isoweekday() == 1` with `_is_reminder_day()`, which compares against `calendar.MONDAY`. That constant is `0`, so the Monday check could never be true. The weekly close reminders for triage and stable cases stopped sending. The daily triage reminders kept going because they don't use this check.
- **Deploy:** Image `main-81d8ae42` rolled out to the scheduler and web pods on 2025-08-13 at 16:40 UTC. The commit is in that image and not in the previous one, `main-b05613b5`.
- **Evidence:** Close reminders went out on Mondays 07-28, 08-04 and 08-11, which were before the rollout. None went out on Monday 08-18. The logs end 08-20, so later Mondays aren't covered.
- **Evening TypeError:** `case_close_reminder` computes `datetime.utcnow() - case.triage_at`. Some cases are in triage status with `triage_at` NULL, which raises the TypeError. The per-case `try` catches it, so the job logs it and skips that case. I haven't confirmed which code path leaves `triage_at` unset. The reopen button handler is the likeliest, since it sets the status without running the flow that stamps the timestamp.
- **Fixes (uncommitted, not deployed):**
  - `_is_reminder_day()` is back to `isoweekday() == 1`, with a regression test that fails on the broken constant.
  - The close reminder counts from `created_at` when `triage_at` is missing, with a test that reproduces the TypeError without the fix.
  - Full suite: 370 passed, 4 skipped. Eight failures in the `ai`, `database`, and `entity` tests also fail on clean `main`, so they predate these changes.
- **Not yet done:** Missed Monday reminders from 08-18 onward aren't resent automatically. The fix also needs to be committed and deployed.

**Report fields**

```
FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e
DEPLOYED_IMAGE: main-81d8ae42
FIRST_MISSED: 2025-08-18
MISSING_FIELD: triage_at
```