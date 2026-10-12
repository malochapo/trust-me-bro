## Recap

**Weekly reminders stopped after a regression.** Since the 2025-08-18 Monday run, assignees have not received the weekly close and stable reminders. The daily triage reminders kept working because they don't use the weekday check.

- **Cause:** commit `c509d45e` (2025-08-12, "refactor(case): share the weekly reminder check") moved the Monday check into `_is_reminder_day()`. It compares `date.today().isoweekday()`, where Monday is 1, with `calendar.MONDAY`, where Monday is 0. The comparison is never true, so the gate blocks every reminder on every day. The original code compared against `1`, which was correct.
- **Deploy:** the scheduler pod (`scheduler-mhtsgqwwx-q5q2n`) started on image `main-81d8ae42` at 2025-08-13T16:40Z. That commit contains `c509d45e`. Monday 2025-08-11 ran before the deploy and was unaffected.
- **Evidence:** on 2025-08-18, `case_stable_reminder` and `case_close_reminder` both ran at 18:00 UTC and sent nothing.
- **Fix:** `_is_reminder_day()` now uses `date.today().weekday()`. Regression test: `tests/case/test_case_scheduled.py::test_is_reminder_day`, parametrized over Monday, Sunday, Tuesday and Saturday. It fails on the broken line and passes on the fix.

**Evening TypeError: cases in triage with no `triage_at`.** `case_close_reminder` computed `datetime.utcnow() - case.triage_at`. A triage case with a null `triage_at` raised `TypeError`. The per-case `try/except` caught it, so it was logged every evening and those cases never got a reminder.
- **Why `triage_at` is null:** it is only set in `case_triage_status_flow`. Three paths reach triage without running it: the dispatcher's catch-all `(_, triage)` branch (which only logs a warning), the Slack reopen button (`plugins/dispatch_slack/case/interactive.py:1427`), and the direct status assignment in `case/service.py:380`. I could not confirm which path produced the production rows, because the logs have no case IDs or transition records.
- **Fix:** the job now counts from `case.triage_at or case.created_at`. Tests in the same file cover a null `triage_at` on a case created 10 days ago (sends, previously failed with the TypeError) and on one created 2 days ago (does not send).
- **Not changed:** the transitions that leave `triage_at` empty still exist, so nulls will keep appearing. Fixing them is a separate change.

**Test status:** `tests/case` passes, 21 tests. The full suite has 8 failures that also fail on unmodified code: 6 in `tests/ai/test_ai_service.py`, which need network access, plus `test_restricted_case_filter_with_test_data` and `test_find_entities_with_field_only`.

**Working tree:** `src/dispatch/case/scheduled.py` is modified and `tests/case/test_case_scheduled.py` is new. Nothing is committed.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e
DEPLOYED_IMAGE: main-81d8ae42
FIRST_MISSED: 2025-08-18
MISSING_FIELD: triage_at