The function is `find_schedule_and_send` in `src/dispatch/feedback/service/scheduled.py`. It counts incidents where the person is commander and cases where they are assignee and the case has a channel, then sums the active participants on each. The window is `hours_in_shift`, which is the shift length from the paging tool's start and end times. When the paging tool gives no shift start (`current_oncall["shift_start"]` is empty), it falls back to 7 days (168 hours), counted back from now.

The lookback helpers `incident/service.py:124` and `case/service.py:109` filter only on `created_at` and take no project argument, so incidents they led in other projects are counted. The same applies to cases.

FILE: src/dispatch/feedback/service/scheduled.py
FUNCTION: find_schedule_and_send
FALLBACK_WINDOW: 7 days
OTHER_PROJECTS: yes