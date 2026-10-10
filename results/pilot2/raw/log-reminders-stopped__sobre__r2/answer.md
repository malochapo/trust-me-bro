The log confirms it: close reminders went out on Mondays 07-28, 08-04 and 08-11, and none since the Aug 12 refactor.

The refactor in `c509d45e` replaced `date.today().isoweekday() == 1` with a new helper, `_is_reminder_day()`. The helper compares `isoweekday()` to `calendar.MONDAY`. `isoweekday()` runs 1 to 7, so Monday is 1. `calendar.MONDAY` is 0, because the `calendar` module counts weekdays from 0. The comparison can therefore never be true, and the weekly close reminders for triage and stable cases are never sent.

The daily triage reminder doesn't use the helper, which is why it kept arriving. The `unsupported operand type(s) for -: 'datetime.datetime' and 'NoneType'` errors in the logs are a separate, older problem. They appear from 07-28, before the refactor, and are not what stopped the reminders.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
CAUSE: It compares `date.today().isoweekday()` (Monday is 1) with `calendar.MONDAY` (which is 0), so it is never true and the weekly Monday reminders are never sent.
INTRODUCED_BY: c509d45e97f4eeacf950450c142ee27da8fcda3f