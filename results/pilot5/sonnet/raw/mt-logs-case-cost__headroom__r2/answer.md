## Recap

**Cost inflation**
- **Root cause:** commit `20f33137` changed `min(timestamps)` to `max(timestamps)` in `get_participant_role_time_seconds()`. The cost cut-off is meant to be the earliest of `stable_at`, `escalated_at` and `closed_at`. With `max`, a case that has several of those timestamps keeps accruing cost until the latest one.
- **Deploy:** it shipped in the Sep 2 18:14Z rollout of `dispatch:main-65f7df6e`. The Sep 4 image `main-51546e13` also carries it, but it did not introduce it.
- **Symptom:** case 5363 jumped from $2,261 to $6,241 when it was marked stable on Sep 9.
- **Fix:** `min` is restored, and a regression test sets all three timestamps and asserts the cut-off is the earliest.
- **Cleanup:** warehouse rows computed since the deploy are still inflated and need recomputing. The affected cases are mainly Stable, Escalated and Closed ones.

**Hourly TypeError**
- **Cause:** `get_hourly_rate()` in `case_cost/service.py` divides the project's annual employee cost by its business year hours, and both columns are nullable. The error text is `'NoneType' and 'int'`, so the left operand, the annual employee cost, was NULL. Each affected case failed in the hourly job and got no cost update.
- **Fix:** it now falls back to the `Project` model's column defaults for either missing value, and a new test covers it.
- **Open question:** I couldn't determine from the logs why it began on Sep 8, so check which project has a NULL annual employee cost.
- **Still exposed:** `incident_cost/service.py` has the same bug and is not fixed.

**Status**
- `tests/case_cost` passes, but I haven't run the full suite and nothing is committed.
- I haven't verified case 5363's actual timestamps in the database.

**FIRST_INFLATED caveat:** the cost-sync log's first flagged jump is case 5284 on 2025-09-03. A smaller inflation on Sep 2 between 18:14Z and midnight would not show as flagged, but I found no diff over $400 in that window. The deploy itself was Sep 2 at 18:14Z.

FILE: src/dispatch/case_cost/service.py
FUNCTION: get_participant_role_time_seconds
INTRODUCED_BY: 20f33137
DEPLOYED_IMAGE: main-65f7df6e
FIRST_INFLATED: 2025-09-03
MISSING_SETTING: annual_employee_cost