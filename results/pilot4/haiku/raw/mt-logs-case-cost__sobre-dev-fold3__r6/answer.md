Here is the recap for the incident report.

**Summary**

Since early September, case response costs for Stable cases were inflated. Costs kept accruing after the case should have frozen, so finance's warehouse received values several times too high. Separately, the hourly scheduler job logged a TypeError for some projects, so those cases got no cost.

**Cost inflation**
- Commit `20f33137` ("fix(case_cost): use the latest status timestamp as the cost cut-off") changed `min(timestamps)` to `max(timestamps)` in `get_participant_role_time_seconds`. The cut-off became the latest of stable/escalated/closed instead of the earliest.
- A case escalated before it was marked stable kept accruing cost up to the stable time. Case 5363 was flat at 2261 from Sep 5 to Sep 9, then jumped to 6241 when it was marked stable.
- The commit reached production in image `main-65f7df6e`, which rolled out to dispatch-web and dispatch-scheduler on Sep 2 at 18:14–18:15 UTC.
- The first flagged inflation was case 5284 on Sep 3 at 11:20 UTC. The cost-sync log only flags large jumps, so smaller inflation before that can't be ruled out.
- Fix: restored `min`, which matches the function's own comment. Added `test_case_cost_cut_off_is_earliest_status_timestamp`, which fails on the buggy code.

**Hourly TypeError**
- `get_hourly_rate` in `src/dispatch/case_cost/service.py` divided `annual_employee_cost` by `business_year_hours` without checking for None. The scheduler logged 708 of these from Sep 8 onward.
- Fix: missing values fall back to the project model's defaults, now named constants in `src/dispatch/project/models.py`. Added two tests covering the fallback.
- Still open: what nulled these project fields is not established.

**Not verified or not done**
- Warehouse values for affected cases are not corrected. The hourly job should pick up the fixed values on later runs, but I haven't confirmed that.
- The fixes are uncommitted and not deployed.
- `incident_cost/service.py` has the same unguarded `get_hourly_rate`. The logs show no errors from it, and I didn't change it.

FILE: src/dispatch/case_cost/service.py
FUNCTION: get_participant_role_time_seconds
INTRODUCED_BY: 20f33137d520c7472bf9f634b29b730bd83f860e
DEPLOYED_IMAGE: main-65f7df6e
FIRST_INFLATED: 2025-09-03
MISSING_SETTING: annual_employee_cost