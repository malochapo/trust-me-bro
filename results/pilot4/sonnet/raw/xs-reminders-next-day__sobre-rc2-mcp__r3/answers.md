**Root cause:** commit `c509d45e` ("refactor(case): share the weekly reminder check", Jordan Lee, 2025-08-12) broke the Monday check in `src/dispatch/case/scheduled.py`.

The old code tested `date.today().isoweekday() == 1`. The refactor moved this into a helper, `_is_reminder_day()`, which tests `date.today().isoweekday() == calendar.MONDAY`. The two use different numbering:
- `isoweekday()` runs from 1 (Monday) to 7 (Sunday).
- `calendar.MONDAY` is 0, because the `calendar` module counts from Monday = 0.

So the helper compares against 0, which `isoweekday()` never returns. It is always false, and both `case_close_reminder` (triage) and `case_stable_reminder` (stable) silently skip the weekly send. The daily triage reminder is a separate job, so it keeps working. The fix will be either `isoweekday() == 1` or `weekday() == calendar.MONDAY`. I haven't changed anything.

**The deploy:** the image `registry.example.com/dispatch:main-81d8ae42`, rolled out on 2025-08-13 at about 16:40Z.
- The scheduler pod `scheduler-mhtsgqwwx-q5q2n` and the web pod `web-5dkmr9s9s-xxktx` both started on that image.
- The previous image was `main-b05613b5`, deployed on 2025-07-30. It does not contain `c509d45e`, while `81d8ae42` does.

**Evidence in the logs:**
- Monday 08-04 and Monday 08-11 (old image): 6 and 5 "Case close reminder sent" lines at 18:00.
- Monday 08-18 (new image): 0 case close reminders. Only the incident close reminder went out.
- 08-11 is the last Monday before the deploy, which fits the "mid-August" start.

**Separate issue, not the cause:** the scheduler log shows 40 `TypeError: ... datetime - NoneType` errors, from cases with no `stable_at` or `triage_at`.
- Commit `32fa810f` ("not all cases have a stable_at date") fixed the `stable_at` side. It is also not in the old image, so it only shipped with the 08-13 deploy.
- On 08-18 and 08-19, `case_close_reminder` still errors at `scheduled.py:47` on `triage_at`. This is a latent bug and could hide further cases, but the weekly reminders would have been skipped even without it.

I'd also add a test that `_is_reminder_day()` is true on a Monday date, since nothing caught this.

----- next turn -----

Assignees have not received the weekly close reminders since the Monday after a refactor shipped. I fixed the check, and the new tests pass with the fix and fail on the old code.

**Cause:** commit `c509d45e` ("share the weekly reminder check") replaced `date.today().isoweekday() == 1` with `_is_reminder_day()`. The new helper compares `isoweekday()` to `calendar.MONDAY`. `isoweekday()` returns 1 for Monday, but `calendar.MONDAY` is 0. The condition is never true, so both the close and the stable reminders silently stopped. No errors are logged.

**Evidence from the logs:**
- The scheduler log shows "Case close reminder sent" on 2025-07-28, 08-04 and 08-11, and never again.
- The commit was made on 2025-08-12 and went out in image `main-81d8ae42`, started on 2025-08-13T16:40. The previous image was `main-b05613b5`.
- The first Monday after that deploy is 2025-08-18.

**Fix:** `_is_reminder_day()` in `src/dispatch/case/scheduled.py` now uses `date.today().weekday() == calendar.MONDAY`, which compares like with like. I left `calendar` imported and added a comment on the off-by-one.

**Tests:** I added `tests/case/test_case_scheduled.py`. It checks `_is_reminder_day()` for 14 consecutive days. It also checks that `case_close_reminder` sends only on a Monday, for a case triaging 10 days. All 16 pass with the fix. Against the old code, 3 of them fail. I did not run the rest of the suite.

I did not write a separate test for `case_stable_reminder`. It shares the same helper, so the helper test covers it.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e97f4eeacf950450c142ee27da8fcda3f
DEPLOYED_IMAGE: registry.example.com/dispatch:main-81d8ae42
FIRST_MISSED: 2025-08-18