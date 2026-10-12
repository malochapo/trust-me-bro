## Recap

**Weekly reminders silent since 2025-08-18.** Commit `c509d45e` ("refactor(case): share the weekly reminder check") replaced the literal `1` with `calendar.MONDAY`, which is `0` in Python. `date.isoweekday()` returns `1` for Monday, so `_is_reminder_day()` was always False. The weekly close and stable reminders never sent. The change reached production in deploy `main-81d8ae42` on 2025-08-13 at 16:40. The last Monday with reminders was 2025-08-11, under the old code. The daily triage reminders were unaffected. The fix changes `isoweekday()` to `weekday()`, and a regression test covers the weekday check.

**Evening TypeError from the close reminder.** `case_close_reminder` computed `datetime.utcnow() - case.triage_at`. Some cases in triage have no `triage_at`, and subtracting `None` raised the `TypeError`. The per-case `try/except` contained it, so the rest of the batch still ran, but the affected cases got no reminder. `triage_at` is set only by the triage transition flow, and some paths enter triage without it, such as the Slack reopen button. I did not confirm which path produced the NULLs in production data. The fix counts from `created_at` when `triage_at` is missing. Tests cover both fallback and precedence.

**Not yet done:** the stable-reminder `None` guard from `32fa810f` is already in production, but the weekday fix and the `created_at` fallback are uncommitted in the working tree. The triage flow gap is still open.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e
DEPLOYED_IMAGE: main-81d8ae42
FIRST_MISSED: 2025-08-18
MISSING_FIELD: triage_at