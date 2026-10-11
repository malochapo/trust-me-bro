Both bugs are fixed in the working tree, and nothing is committed. The weekday check at `src/dispatch/case/scheduled.py:33` and the close reminder's `triage_at` fallback at lines 47-50 are the two changes. Regression tests cover both: `tests/case/test_case_scheduled.py` has 10 tests, all passing, and `python -m pytest tests/case` gives 25 passed.

What happened:
- **Missing Monday reminders:** commit `c509d45e` (2025-08-12) replaced `isoweekday() == 1` with `isoweekday() == calendar.MONDAY`, but `calendar.MONDAY` is 0. The Monday check could never be true, so case close and stable reminders stopped. The daily triage reminder has no Monday check, so it kept going.
- **Evening TypeError:** `triage_at` was added in 2022 without a backfill, and it is only set by a background flow. Triage cases without it made `datetime.utcnow() - None` fail every evening. The job now counts those cases from `created_at`.
- **Deploy:** the scheduler started running image `main-81d8ae42` on 2025-08-13 at 16:40, which contains `c509d45e`. The Monday 2025-08-11 run was on the older image and sent six close reminders. The Monday 2025-08-18 run sent none.

Caveats: the logs don't include case IDs, so I can't say how many cases hit the TypeError. I also haven't confirmed the image-tag-to-commit mapping against the deploy pipeline.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e
DEPLOYED_IMAGE: main-81d8ae42
FIRST_MISSED: 2025-08-18
MISSING_FIELD: triage_at