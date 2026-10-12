**Root cause:** the Monday gate in `src/dispatch/case/scheduled.py` can never be true. The check is `date.today().isoweekday() == calendar.MONDAY` (lines 31–33). `isoweekday()` returns 1 for Monday, but `calendar.MONDAY` is 0 in Python, so `_is_reminder_day()` is always False. Both `case_close_reminder` (triage) and `case_stable_reminder` call it, so neither sends anything.

**Commit that introduced it:** `c509d45e` "refactor(case): share the weekly reminder check" (2025-08-12, Jordan Lee). The refactor moved the old `date.today().isoweekday() == 1` into the helper and changed the literal to `calendar.MONDAY`.

**Deploy that shipped it:** image `registry.example.com/dispatch:main-81d8ae42`, which is main at `81d8ae42` and contains `c509d45e`. The logs show the web pod `5dkmr9s9s-xxktx` and scheduler pod `mhtsgqwwx-q5q2n` starting on that image at about 2025-08-13 16:40Z. The scheduler pod before that, `xdp7k6gs2q-w6cj7`, was still running the old code on 2025-08-12.

**Evidence:**
- Monday 2025-08-04 and Monday 2025-08-11 both logged "Case close reminder sent" (15 total, all on those two Mondays or 07-28). Monday 2025-08-18 logged none.
- Daily triage reminders kept sending after the deploy. `case_triage_reminder` has no weekday gate, which fits the symptom.
- Incident weekly reminders still work. `incident/scheduled.py:229` compares against the literal `1`, not `calendar.MONDAY`.

**Fix (not applied):** use `calendar.MONDAY + 1`, or better, compare `date.today().weekday() == calendar.MONDAY`, which is the consistent pair. Add a test that pins the reminder day to a Monday date. The existing test suite did not catch this.

**Two things I noticed that are separate from the root cause:**
- `32fa810f` ("not all cases have a stable_at date") shipped in the same release. It fixed the daily `NoneType` errors in `case_stable_reminder`, and those stopped after 2025-08-12.
- `case_close_reminder` has no equivalent guard for `triage_at`. It still logs a `TypeError` for each affected case every day, from 2025-08-13 onward. Those cases are skipped, not failed, but it is still noise.

I corrected nothing in the code, as you asked. I recorded the finding in sobre's session log. That entry calls the stable-case error an "AttributeError-style" error, which is wrong: it is a `TypeError`.

----- next turn -----

Everything is saved, so tomorrow's session can pick it up from either place:

- **sobre session log:** the root-cause finding, a correction, the planned fix as a decision, and the open items as a task. Call `sobre_session` with `action="load"` to see them.
- **Memory note:** `weekly-reminder-monday-bug.md` in the project memory folder, plus a one-line pointer in a new `MEMORY.md`. Both files are new, since the index didn't exist before.

**Summary of what's saved:**
- **Cause:** `_is_reminder_day()` in `src/dispatch/case/scheduled.py` compares `isoweekday()` (Monday = 1) with `calendar.MONDAY` (Monday = 0), so it is never true.
- **Introduced by:** `c509d45e`, 2025-08-12.
- **Shipped in:** `registry.example.com/dispatch:main-81d8ae42`, rolled out about 2025-08-13 16:40Z.
- **Open:** apply the fix (`weekday() == calendar.MONDAY`) with a regression test, decide on a `triage_at` None guard in `case_close_reminder`, and confirm the stable-case reminder should go out once the gate is fixed.

No code has been changed. Earlier I mislabeled the stable-case error as `AttributeError`. It is a `TypeError`, and the correction is in the session log.

----- next turn -----

The Monday reminder gate is fixed in the working tree, with a regression test. I haven't committed it, since you didn't ask for a commit.

**The bug:** `_is_reminder_day()` compared `date.today().isoweekday()` (Monday = 1) with `calendar.MONDAY` (Monday = 0), so it was never true. Commit `c509d45e` introduced it, and it shipped in `main-81d8ae42` on 2025-08-13. The scheduler log shows case close reminders went out on Monday 2025-08-11 and none on 2025-08-18.

**The fix:** `src/dispatch/case/scheduled.py` now uses `date.today().weekday() == calendar.MONDAY`.

**The test:** `tests/case/test_case_scheduled.py` checks the gate for each day of one week. On the original code the Monday case fails, and it passes with the fix.

**Test run:** the full suite gives 366 passed, 4 skipped, 8 failed. The 8 failures are in `tests/ai/test_ai_service.py`, `tests/database/test_service.py` and `tests/entity/test_entity_service.py`. They fail the same way with my change stashed, so they predate it.

**Left out of scope:** the logs show a daily `TypeError` in `case_close_reminder` when `triage_at` is `None`. That job has no guard for it, unlike the stable reminder. It is unrelated to the weekday bug, so I did not change it. It is noted in the memory file.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e97f4eeacf950450c142ee27da8fcda3f
DEPLOYED_IMAGE: main-81d8ae42
FIRST_MISSED: 2025-08-18