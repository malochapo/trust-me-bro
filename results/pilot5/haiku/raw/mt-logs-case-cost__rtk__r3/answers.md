The root cause is `20f33137`, and it shipped in the `main-65f7df6e` build. It is not the cost-sync 1.5.0 bump. I didn't change any code.

## Root cause

Commit `20f33137` ("fix(case_cost): use the latest status timestamp as the cost cut-off", Jordan Lee, 2025-09-02) changes one line in `get_participant_role_time_seconds` in `src/dispatch/case_cost/service.py:353`:

```diff
-            participant_role_renounced_at = min(timestamps)
+            participant_role_renounced_at = max(timestamps)
```

For a case that is no longer New or Triage, `timestamps` holds whichever of `stable_at`, `escalated_at` and `closed_at` are set. That list is the cut-off for a participant's time in the case. The original `min` stops the clock at the earliest of those events. The new `max` stops it at the latest, so any case with an escalation or closure after its stable time gets billed for the extra time.

Three things point to this being a mistake, not a deliberate change:
- The comment directly above the block says "Determine the earliest relevant timestamp for cost calculation cut-off". The `max` contradicts it.
- The commit title says "latest status timestamp", but the existing behaviour and the test `test_case_cost_stops_at_stable_time` (`tests/case_cost/test_case_cost_service.py:355`) both say costs stop at the first stable/escalation point.
- No test covers `escalated_at` or `closed_at`, so the change passed CI.

## Which deploy shipped it

The events log shows the Dispatch image tags rolled out:

| Image | Rolled out | Contains `20f33137`? |
|---|---|---|
| `main-b01a1aba` | before 2025-08-26 | no |
| `main-3e0445ff` | 2025-08-27 17:03 | no |
| **`main-65f7df6e`** | **2025-09-02 18:14** (db-upgrade, then web and scheduler at 18:15) | **yes, first build** |
| `main-51546e13` | 2025-09-04 16:52 | yes |

`git merge-base --is-ancestor` confirms `20f33137` is an ancestor of `65f7df6e` and not of `3e0445ff`.

## Timeline matches

The cost-sync log flags a case when its classic cost jumps more than 100% between hourly syncs while it is Stable. There are five such flags, and all come after the Sep 2 deploy:

- 5284: 3331 → 8804, Sep 3 11:20
- 5327: 2244 → 5539, Sep 5 16:20
- 5264: 3285 → 11987, Sep 8 10:20
- 5363: 2261 → 6241, Sep 9 12:20
- 5406: 1975 → 4945, Sep 12 11:20

Before Sep 2 there are no such flags.

## Ruled out

- **cost-sync 1.5.0.** The finance job went from 1.4.2 to 1.5.0 on Sep 1 at 10:20. Its hourly diffs for the rest of the period look like ordinary growth, and the jumps begin after the Sep 2 Dispatch deploy, not at the version bump.
- **`main-3e0445ff` and `main-51546e13`.** The first is a DB-upgrade build from before the commit. The second is a later build that carries the same bug but doesn't introduce it.
- **Hourly rates and cost models.** Nothing in `src/dispatch/case_cost`, `case_cost_type` or `cost_model` changed other than `20f33137` in this window.

## Gaps

- The logs don't include the `stable_at`, `escalated_at` and `closed_at` values for these cases, so I can't reproduce the exact amounts, such as 2261 → 6241, from the code. To confirm, check case 5363's timestamps in Dispatch. If it has an `escalated_at` or `closed_at` later than `stable_at`, `max` moves the cut-off to that later time, and the cost difference should match.
- The sync only flags cases that went over 100%, so smaller over-counts may be hidden.

## Suggested fix (not applied)

Revert line 353 to `min(timestamps)`, which matches the comment and the test. Add test cases for `escalated_at` and `closed_at` so this doesn't come back. Once the fix ships, the affected cases will need their costs recomputed in the warehouse, which is a finance-side decision.

----- next turn -----

The fix is in and the regression test is in place. Both pass, and the new test fails on the buggy code. I haven't committed anything.

**The fix**: `src/dispatch/case_cost/service.py:353` changes `max(timestamps)` back to `min(timestamps)`. The cost cut-off is again the earliest of stable, escalated or closed, which matches the comment above it.

**The regression test**: `test_case_cost_stops_at_earliest_cutoff_timestamp` in `tests/case_cost/test_case_cost_service.py`. It sets `escalated_at` one hour ago and `stable_at` 30 minutes ago, then asserts that the participant's time stops at the escalation. The existing test only set `stable_at`, which is why the `max` change passed CI.

**Verification**:
- With the fix, `tests/case_cost`, `tests/case` and `tests/incident_cost` pass (50 tests).
- With `max` reintroduced, the new test fails (1 failed, 19 passed in `tests/case_cost`).

**Deviation from your instructions**: I did not run `python -m pytest` as the default interpreter. The repo's venv (`venv/bin/python`) has no pip and no dependencies, and the sandbox can't reach PyPI to install them. I ran the tests with the system Python 3.11 and the dependency set left in the scratchpad (`/tmp/claude-0/.../bench-venv/deps`), with `src` on `PYTHONPATH`:

```
PYTHONPATH=<deps>:$PWD/src /usr/bin/python3.11 -m pytest tests/case_cost -q
```

PostgreSQL was reachable from that run. The venv's broken dependency setup isn't fixed, so `python -m pytest` in that venv will still fail until its dependencies are reinstalled.

**Still open**: the cost values already written to the finance warehouse for the affected cases (5284, 5327, 5264, 5363, 5406 and others) are still inflated. Recomputing them is a finance decision, so I haven't touched it.

----- next turn -----

The `TypeError` is fixed and covered by a new test. Cases whose project has no annual employee cost or no business year hours now get a cost, using the project model's defaults (50000 and 2080).

**Cause**: `get_hourly_rate` in `src/dispatch/case_cost/service.py` divides `annual_employee_cost` by `business_year_hours` without checking for `None`. The logs show 708 errors from 2025-09-08 15:55 onward, all with this traceback. The scheduler catches the exception per case and skips that case, which is why those cases got no cost. The logs don't name the affected projects.

**Fix**: each missing value falls back to the default declared on the `Project` columns, read via `Project.__table__.c.<column>.default.arg`, so the defaults stay in one place. I also added the `Project` import to the module.

**Tests**: `test_get_hourly_rate_uses_project_defaults_for_missing_values` in `tests/case_cost/test_case_cost_service.py` covers both values missing, only the cost missing, only the hours missing, and a full cost calculation that previously raised. It fails on the original code and passes with the fix. `tests/case_cost`, `tests/case` and `tests/incident_cost` pass (51 tests).

**Things to know**:
- **Root cause of the NULLs is unconfirmed.** The column defaults only apply on INSERT, so a project saved with an explicit `None` stays NULL. The project schema allows `None`, and `individual/service.py` already patches `None` to the same defaults. I haven't found which write path produced the NULLs for these projects. Finding the affected projects in the database would settle it.
- **`incident_cost/service.py:131` has the same unguarded `get_hourly_rate`.** The logs show no errors from the incident job, but it would fail the same way. I left it alone because you asked about the case job. It's a small change if you want it.
- **Test command**: as before, the venv has no dependencies, so I ran `/usr/bin/python3.11 -m pytest` with the scratchpad dependency set and `src` on `PYTHONPATH`.
- Nothing is committed.

----- next turn -----

Recap for the incident report:

**Inflated case costs.** Commit `20f33137` changed `min(timestamps)` to `max(timestamps)` in `get_participant_role_time_seconds`. That function sets the cut-off for a participant's time in a case, which should be the earliest of stable, escalated or closed. With `max`, the cut-off moved to the latest of those events, so time was billed after the case had stabilised or escalated. The code comment says "earliest", and the existing test only covered `stable_at`, so CI didn't catch it. The commit shipped in build `main-65f7df6e`, rolled out on 2025-09-02 at 18:14. The first clearly inflated cost is case 5284 on 2025-09-03 (3331 → 8804, +5473 in one hour). The pre-deploy hourly delta has a median of 97 and a maximum of 221. Case 5323 on 2025-09-02 19:20 rose by 230, which is within normal variation for a high-cost case, so I didn't count it. The logs don't include the case timestamps, so the per-case mechanism is inferred from the code and not yet confirmed against Dispatch's database. The fix (revert to `min`) and a regression test are in the working tree, not committed.

**Hourly TypeError (separate bug).** Since 2025-09-08 15:55, `get_hourly_rate` in the same file has divided `annual_employee_cost` by `business_year_hours` without a `None` check. That raised a TypeError for 708 cases, which the scheduler caught and skipped, so those cases got no cost. Missing values now fall back to the `Project` column defaults (50000 and 2080), with a test. I haven't confirmed how the NULLs were written, and the logs don't name the affected projects. The same unguarded function exists in `incident_cost/service.py`, which I left unchanged.

FILE: src/dispatch/case_cost/service.py
FUNCTION: get_participant_role_time_seconds
INTRODUCED_BY: 20f33137d520c7472bf9f634b29b730bd83f860e
DEPLOYED_IMAGE: main-65f7df6e
FIRST_INFLATED: 2025-09-03
MISSING_SETTING: annual_employee_cost