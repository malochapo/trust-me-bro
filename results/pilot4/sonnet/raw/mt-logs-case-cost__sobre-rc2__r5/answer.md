Checking the last details for the recap: the cost-sync version history and the first inflated case in the data.

**Recap**

1. **Cost inflation.** Commit `20f33137` changed `min(timestamps)` to `max(timestamps)` in the case-cost cut-off. Cases with more than one of `stable_at`, `escalated_at` and `closed_at` were billed up to the latest one instead of the earliest. The commit is on `main`, and `65f7df6e` is the first image built after it. That image went to production on 2025‑09‑02 at about 18:14Z.
2. **Evidence.** The cost-sync job flagged no case before 2025‑09‑03T11:20Z. Its first jump is case 5284 (3331 → 8804). I scanned every sync diff from 09‑02 16:00Z to 09‑03 12:00Z for a rise of more than 400, and 5284 was the only one. Four more cases were flagged later: 5327, 5264, 5363 and 5406. Smaller inflations may not have been flagged, so treat 2025‑09‑03 as the first inflated case that shows up in these logs.
3. **Correction to my first answer.** I said the finance job stayed on `case-cost-sync:1.4.2` throughout. That was wrong. It moved to 1.5.0 on 2025‑09‑01 (first 1.5.0 run at 10:20Z). That is still before the bug shipped, and the 1.5.0 runs before 09‑02 flagged nothing. So I don't see the version change as a cause, but it should be in the report as a change in the same period.
4. **TypeError.** `get_hourly_rate()` divided a NULL `annual_employee_cost` (the traceback's `NoneType / int`) because the project columns are nullable. The code is old, so I think a data change triggered it, and the logs can't confirm that. It occurs 708 times from 2025‑09‑08 15:55. A NULL `business_year_hours` would be a separate failure with the operands reversed. Both are now defaulted.
5. **State of the fixes.** Both fixes and their tests are written and passing, but they are uncommitted and not deployed. Finance still needs to overwrite the warehouse rows from 09‑02 onward.

FILE: src/dispatch/case_cost/service.py
FUNCTION: get_participant_role_time_seconds
INTRODUCED_BY: 20f33137
DEPLOYED_IMAGE: registry.example.com/dispatch:main-65f7df6e
FIRST_INFLATED: 2025-09-03
MISSING_SETTING: annual_employee_cost