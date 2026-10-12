## Recap

**Symptom:** Since mid-August, assignees stopped getting the Monday reminders to close long-running triage and stable cases. Daily triage reminders kept arriving.

**Root cause:** Commit `c509d45e` ("refactor(case): share the weekly reminder check", 2025-08-12) moved the Monday check into `_is_reminder_day()`, which compared `date.today().isoweekday()` (Monday = 1) with `calendar.MONDAY` (Monday = 0). The comparison was never true, so the close and stable reminders never sent. `case_triage_reminder` has no weekday check, so it kept working.

**Deploy:** Image `main-81d8ae42` started for both `web` and `scheduler` on 2025-08-13 at 16:40 UTC. Commit `c509d45e` is an ancestor of `81d8ae42`. This is the only deploy after the refactor. The image-to-commit mapping comes from the image tag and was not checked against the registry.

**Evidence:** Close-reminder sends happened on Mondays 2025-08-04 and 2025-08-11, both before the deploy. None happened on 2025-08-18, the first Monday after the deploy.

**Fix:**
- `_is_reminder_day()` now uses `date.today().weekday() == calendar.MONDAY`.
- `case_close_reminder` counts from `created_at` when `triage_at` is missing, so those cases get their weekly reminder.

**Tests:** `tests/case/test_case_scheduled.py` has 13 tests. They cover the weekday check across a full week, the stable and close reminders on Monday and on other days, and the `created_at` fallback. Against the old code, the Monday and fallback tests fail. With the fix, all 28 tests in `tests/case` pass. The full suite has 8 failures in AI, database, and entity tests. They also fail without my change, so they are unrelated.

**Not changed:**
- `case_stable_reminder` still skips cases with no `stable_at`, so those cases get no weekly stable reminder. You asked for the fallback only on the close job. Say if you want the same `created_at` fallback there.
- Nothing is committed. The changes are in the working tree.

---

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e
DEPLOYED_IMAGE: main-81d8ae42
FIRST_MISSED: 2025-08-18
MISSING_FIELD: triage_at