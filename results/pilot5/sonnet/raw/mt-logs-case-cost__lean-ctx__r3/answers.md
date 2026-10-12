## Root cause

The cause is commit **`20f33137`**, "fix(case_cost): use the latest status timestamp as the cost cut-off" (Jordan Lee, 2025-09-02 09:29 -0700). It changed one line in `get_participant_role_time_seconds()` in `src/dispatch/case_cost/service.py:353`:

```python
- participant_role_renounced_at = min(timestamps)
+ participant_role_renounced_at = max(timestamps)
```

`timestamps` holds the case's `stable_at`, `escalated_at` and `closed_at`. The original code stopped billing at the earliest of them, so a case stopped accruing cost once it went stable (or escalated or closed). The commit title says "latest", but the code comment still reads "we use the role's renounced_at time if it happened before the case was marked as stable or closed". It also still says "Determine the earliest relevant timestamp for cost calculation cut-off". So `max` contradicts the surrounding intent.

With `max`, a case that is stable and later escalated or closed is billed up to the latest of those times. A participant role that was never renounced runs to that later time. That is why the cost jumps: the case is billed for the gap between the earliest and latest status timestamps, for every participant role.

The jumps appear in `cost-sync.log` only for cases in `Stable` status, which fits this mechanism:

| Case | Sync time (UTC) | Classic cost |
|---|---|---|
| 5284 | 09-03 11:20 | 3331 → 8804 |
| 5327 | 09-05 16:20 | 2244 → 5539 |
| 5264 | 09-08 10:20 | 3285 → 11987 |
| 5363 | 09-09 12:20 | 2261 → 6241 |
| 5406 | 09-12 11:20 | 1975 → 4945 |

Case 5363 stopped growing at 2261 on 09-05 16:20 and then jumped on 09-09. The `diff` lines in the log show this. The extra cost is the gap between the earlier and later status timestamps.

## The deploy

The deploy that shipped it is **image `registry.example.com/dispatch:main-65f7df6e`, rolled out on 2025-09-02 at about 18:14–18:16Z**. The `events.log` events for it:
- The `dispatch-db-upgrade-65f7df6e` job completed at 18:14:33.
- The `dispatch-scheduler` pod was replaced at 18:14–18:15.
- The `dispatch-web` replicas moved to the new image at 18:14–18:16, and the old replica set was fully scaled down at 18:15:54.

`65f7df6e` is the commit after `20f33137`, and `20f33137` is an ancestor of it, so the image contains the change. The first flagged jump (case 5284) comes about 17 hours after this rollout.

The next deploy, `main-51546e13` on 09-04 at about 16:53Z, is the Slack canvas feature. It still contains the bug but did not introduce it.

## What I ruled out
- **Hourly rates or cost models:** nothing in the logs or the diff touches them.
- **case-cost-sync upgrade:** the 1.4.2 → 1.5.0 upgrade happened earlier, on 09-01 at 10:20Z. The first jump came two days later, after the Dispatch deploy.
- **Other events:** the readiness-probe failures, HPA rescales and the image-pull 502 on 08-27 are unrelated noise.

## Caveats
- The logs don't show the case status transitions themselves, only the cost deltas. That the jump comes from the later of `stable_at`, `escalated_at` and `closed_at` is inferred from the code and the Stable-only pattern.
- Your note says case 5363 was marked stable on September 9. The cost had already stopped growing on 09-05 at 16:20, so something changed the case status on 09-05, and 09-09 is when the new, higher number reached the warehouse. I'd confirm the case's status history in the Dispatch DB before telling finance exactly why.
- Every case that was stable and then later escalated or closed since 09-02 18:14Z has probably been over-costed in the warehouse. Cases already synced with inflated values will need a re-sync after a fix, because the warehouse upserts the values it was given.

I haven't changed any code. The fix would be to revert `max` to `min`. If the aim was to bill differently for escalated cases, that needs its own change with tests.

----- next turn -----

I've changed `max(timestamps)` back to `min(timestamps)` in `src/dispatch/case_cost/service.py:353`, and added a regression test.

The new test is `test_case_cost_stops_at_earliest_status_timestamp` in `tests/case_cost/test_case_cost_service.py`. It sets up a case that went stable, was then escalated and then closed, with a participant role that is still active. It checks that the billed time ends at `stable_at`. The existing stable-time test missed the bug because it only set `stable_at`, so `min` and `max` gave the same answer.

All 20 tests in `tests/case_cost` pass with the fix. With the fix stashed (the old `max`), the new test fails and the other 19 pass. I only ran `tests/case_cost`, not the whole suite.

I haven't committed anything. Once this is deployed, the warehouse still needs a re-sync. Cases that went stable and were later escalated or closed since 2025-09-02 18:14Z have inflated costs stored there.

----- next turn -----

The TypeError comes from `get_hourly_rate()` in `src/dispatch/case_cost/service.py`, and it's now fixed. I ran `tests/case_cost` and `tests/incident_cost`; all 36 tests pass.

**Cause:** `get_hourly_rate()` computed `project.annual_employee_cost / project.business_year_hours`. Both columns on `Project` are nullable, and their defaults (50000 and 2080) only apply when a row is inserted. A project with either value NULL therefore raised `unsupported operand type(s) for /: 'NoneType' and 'int'`. The failing call was the new cost model at `calculate_case_response_cost_new`.

The first TypeError in `scheduler.log` is 2025-09-08 15:55:01, and there are 708 of them through 09-14. The logs don't show why those projects have NULLs from that date. Probably the value was cleared in an update, since the project schema accepts `None`. I can't confirm that from the logs.

The scheduler catches errors per case in `case_cost/scheduled.py`, so each failing case lost its cost update (new and classic models) every hour, while other cases were unaffected.

**Fix:** a NULL annual employee cost or NULL business year hours now falls back to the `Project` column default. I read it from `Project.__table__` rather than hard-coding 50000 and 2080 again.

**Test:** `test_get_hourly_rate_uses_project_defaults_for_unset_values` covers both values unset, only the cost unset, and only the hours unset. With the source changes stashed it fails, along with the earlier `min` regression test, which was also reverted by the stash.

Two things I left alone:
- `incident_cost/service.py:131` has the same unguarded division, so incidents on those projects would hit the same error. You asked about cases, so I didn't touch it. It's a small change if you want it.
- Only `None` triggers the fallback. A business year hours value of 0 would still raise `ZeroDivisionError`.

Nothing is committed. The projects with NULLs may be worth correcting in the database too.

----- next turn -----

## Recap

**Cost inflation**
- **Cause:** commit `20f33137` ("fix(case_cost): use the latest status timestamp as the cost cut-off") changed `min(timestamps)` to `max(timestamps)` in `get_participant_role_time_seconds()`. Billing used to stop at the earliest of `stable_at`, `escalated_at` and `closed_at`. It now ran to the latest, so a case that went stable and was later escalated or closed got billed for the gap.
- **Deploy:** the change went to production in image `dispatch:main-65f7df6e`, rolled out on 2025-09-02 at about 18:14–18:16Z. That covered the db-upgrade job, the scheduler and web. The later `51546e13` deploy on 09-04 contains the bug but didn't introduce it.
- **First inflated case:** case 5284 jumped from 3331 to 8804 in the 2025-09-03 11:20Z sync. Five cases show jumps of more than 400 in the logs (09-03, 09-05, 09-08, 09-09, 09-12). Case 5284 is the earliest. I can't rule out smaller inflations earlier than that.
- **Fix:** reverted to `min`, with a regression test (`test_case_cost_stops_at_earliest_status_timestamp`).
- **Still to do:** the warehouse needs a re-sync for affected cases.

**Hourly TypeError (separate bug)**
- **Cause:** `get_hourly_rate()` divided `project.annual_employee_cost` by `project.business_year_hours`. A project with either value NULL raised a TypeError. The column defaults only apply on insert.
- **When:** the errors start 2025-09-08 15:55:01 in `scheduler.log`, and there are 708 through 09-14.
- **Fix:** a NULL value now falls back to the `Project` column default, with a test (`test_get_hourly_rate_uses_project_defaults_for_unset_values`).
- **Unconfirmed:** the logs don't show why those projects have NULLs.
- **Not fixed:** `incident_cost/service.py:131` has the same unguarded division, and 0 business year hours would still divide by zero.

Both fixes are uncommitted in the working tree.

FILE: src/dispatch/case_cost/service.py
FUNCTION: get_participant_role_time_seconds
INTRODUCED_BY: 20f33137
DEPLOYED_IMAGE: registry.example.com/dispatch:main-65f7df6e
FIRST_INFLATED: 2025-09-03
MISSING_SETTING: annual_employee_cost