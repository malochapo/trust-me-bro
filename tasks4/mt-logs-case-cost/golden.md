Recap: a case's classic response cost stops at a cut-off taken from the times it was escalated, marked stable or closed. Commit {plant:q2-case-cost-cutoff} made get_participant_role_time_seconds take the latest of those times instead of the earliest, so a case escalated to an incident and marked stable later was charged for the whole escalation, on top of the incident's own cost. It reached production with the rollout of main-65f7df6e on 2025-09-02. The hourly cost job recomputes a stable case only once, after it is marked stable, so the first inflated cost was case 5284's, on 2025-09-03. The hourly TypeError came from the fraud project, created on 2025-09-08 without an annual employee cost; a missing cost setting now falls back to the project model's default.

FILE: src/dispatch/case_cost/service.py
FUNCTION: get_participant_role_time_seconds
INTRODUCED_BY: {plant:q2-case-cost-cutoff}
DEPLOYED_IMAGE: registry.example.com/dispatch:main-{plant:2a90ae1b9fe5ebf8b5152673d965804a63f98275:short}
FIRST_INFLATED: 2025-09-03
MISSING_SETTING: annual_employee_cost
