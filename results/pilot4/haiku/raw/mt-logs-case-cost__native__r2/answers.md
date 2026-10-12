## Root cause

Commit `20f33137` ("fix(case_cost): use the latest status timestamp as the cost cut-off", Jordan Lee, 2025-09-02 09:29 -0700) changed one line in `get_participant_role_time_seconds` in `src/dispatch/case_cost/service.py`:

```diff
-            participant_role_renounced_at = min(timestamps)
+            participant_role_renounced_at = max(timestamps)
```

The `timestamps` list holds whichever of `stable_at`, `escalated_at`, and `closed_at` are set. Participant time is counted from `assumed_at` up to that cut-off. `min` stops the clock at the first moment the case stopped being active. `max` stops it at the last of those timestamps.

So for any case that was escalated and later marked stable or closed, the cost clock keeps running for the whole gap between the two events. When the later status lands, the cut-off jumps and the cost jumps with it. The commit's own message says "latest", so this looks like a deliberate change of meaning rather than a typo. But the existing test `test_case_cost_stops_at_stable_time` only sets `stable_at`, where `min` and `max` agree, so nothing caught it.

This matches case 5363. Its classic cost sat flat at 2261 from Sep 5 16:20 to Sep 9 12:20. That is consistent with the cut-off being frozen at an earlier timestamp. At 12:20 on Sep 9 the case was marked Stable, and the cost moved to 6241. The logs don't include case status history, so I can't see that case's escalated_at directly. That part is inferred from the code and the timing.

## Deploy that shipped it

- The commit is an ancestor of image `registry.example.com/dispatch:main-65f7df6e`. It is not in `main-3e0445ff`, the previous build.
- `main-65f7df6e` ran the `dispatch-db-upgrade` job at **2025-09-02 18:14:09Z**. The `dispatch-web` rollout followed at 18:14:36Z.
- The `dispatch-scheduler` pods, which run `calculate_cases_response_cost`, were replaced at **2025-09-02 18:15:09–18:15:24Z**. That is the production rollout that started computing the new cut-off.
- `main-65f7df6e` is the head commit `65f7df6e` ("feat(ui): allow filtering by dedicated channel cases", #6206), which bundles 9 commits on top of `3e0445ff`. The offending change came in with that bundle, not as a standalone deploy.

## Things I ruled out or could not verify

- **cost-sync 1.4.2 → 1.5.0** happened on Sep 1, before the Sep 2 deploy. Its source isn't in this repo, so I can't rule it out completely. But the values change inside Dispatch's own calculation, and the job only copies them.
- **Overall pattern:** I checked the hourly diffs, but they are mostly new-case additions with small bases, so they don't isolate the pattern across cases. Case 5363 is the one example I traced in full. The broader "several times" claim across cases is consistent with this mechanism, but I haven't confirmed it case by case.
- **Scheduler errors** on Sep 11 and Sep 13 (`unsupported operand type(s) for /: 'NoneType' and 'int'`, in `case_cost/service.py` around lines 312 and 493) look like a separate problem. I didn't investigate them.

## Suggested fix (not applied)

- Revert the cut-off to `min(timestamps)`, or confirm with the author of `20f33137` that "latest" was intended. If it was, the cost model needs a different rule, not a one-word change.
- Add a test where `escalated_at` and `stable_at` are both set, with the cut-off expected at the earlier one.
- After the fix, the hourly job recomputes costs, so cases affected since Sep 2 should drop back on the next run. Confirm that against the warehouse, since the finance table only receives upserts for changed rows.

----- next turn -----

## Fixed, with a regression test

The cost cut-off is back to `min(timestamps)`, so cost stops at the earliest of `escalated_at`, `stable_at` and `closed_at`. The change is one line in `src/dispatch/case_cost/service.py`, reverting `20f33137`.

**Regression test:** `test_case_cost_stops_at_first_stop_event` in `tests/case_cost/test_case_cost_service.py`. A participant is assigned three hours ago. The case was escalated two hours ago and marked stable one hour ago. The test expects the participant's time to stop at the escalation, two hours after assignment. I checked it against both versions:
- With `max()` restored, it fails.
- With the fix, it passes.

The existing stable-time test only sets `stable_at`, where `min` and `max` agree. That is why the original suite didn't catch the change.

**Test results (local PostgreSQL, `python -m pytest`):**
- `tests/case_cost`: 20 passed, including the new test.
- Full suite with the fix: 8 failed, 360 passed, 4 skipped.
- Full suite on untouched HEAD (stashed and rerun): 8 failed, 359 passed, 4 skipped.

The same 8 tests fail on HEAD, in `tests/ai/test_ai_service.py`, `tests/database/test_service.py::test_restricted_case_filter_with_test_data` and `tests/entity/test_entity_service.py::test_find_entities_with_field_only`. They are pre-existing and unrelated to this change. I did not investigate them.

**Open question:** the commit message says "use the latest status timestamp", so the author may have meant `max` on purpose. I went with `min` because you asked for the fix and the existing test expects cost to stop at the stable time. If the author meant "latest" for some other case, the rule needs a different design, not this one-word change. It may be worth checking with them.

Nothing is committed. The affected warehouse rows should correct on the next hourly recalculation once this is deployed. I haven't verified that against the warehouse.

----- next turn -----

## Cause

Some projects have `annual_employee_cost` or `business_year_hours` stored as `NULL`. `get_hourly_rate` in `src/dispatch/case_cost/service.py` divides one by the other with no check, so every case in such a project raises `TypeError: unsupported operand type(s) for /: 'NoneType' and 'int'`. The scheduler logged 708 of these between Sep 8 and Sep 14, all from `case_cost.scheduled`.

The project model's column defaults (50000 and 2080) only apply when a row is inserted. They don't cover a value that is explicitly set to `NULL` later.

The likely route to `NULL` is the project edit form. In `src/dispatch/static/dispatch/src/project/NewEditSheet.vue`, both fields are `clearable` and use `v-model.number`. Clearing one sends `null`, and `project/service.py:update` (`exclude_unset=True`) writes that `null` to the database. I did not find a project-update log that confirms this for these specific projects. The logs don't name the projects either.

## Fix

- **`get_hourly_rate`** falls back to the project defaults for whichever value is `None`. Zero is still used as given, which keeps the existing behavior.
- **`src/dispatch/project/models.py`** now defines `DEFAULT_ANNUAL_EMPLOYEE_COST = 50000` and `DEFAULT_BUSINESS_YEAR_HOURS = 2080`. The column defaults and the Pydantic defaults both use them, so the fallback and the model can't drift apart.

## Tests

Two tests in `tests/case_cost/test_case_cost_service.py`:
- `test_get_hourly_rate_falls_back_to_project_defaults` checks each field missing alone and both missing together.
- `test_case_cost_with_missing_project_values_uses_defaults` runs the classic cost calculation on a case whose project has both values missing and checks the cost is one hour at the default rate, 25.

On the HEAD version of `case_cost/service.py`, both fail with the same `TypeError`. With the fix they pass.

**Results (`python -m pytest`, local PostgreSQL):** the full suite gives 8 failed, 362 passed, 4 skipped. The 8 failures are the same pre-existing ones from before (`tests/ai/test_ai_service.py`, `tests/database/test_service.py::test_restricted_case_filter_with_test_data`, `tests/entity/test_entity_service.py::test_find_entities_with_field_only`). They also fail on untouched HEAD.

## Notes

- `incident_cost/service.py:133` has the same unguarded division. Its job logs no errors in this period, so I left it alone. It would fail the same way if a project ever had a `NULL` there.
- Projects that already have `NULL` values still have them in the database. This fix makes their costs compute, but it does not clean up the data. You may want a migration or a one-off `UPDATE` for those rows, and a check on whether the edit form should reject clearing these fields at all.
- The `min()` fix from the previous step is still in place. The file was changed on disk between my edits. I checked the current diff, and it contains only my intended changes.
- Nothing is committed.

----- next turn -----

## Recap

**Cost bug:** Commit `20f33137` ("fix(case_cost): use the latest status timestamp as the cost cut-off") changed `min(timestamps)` to `max(timestamps)` in `get_participant_role_time_seconds`. The cut-off is the earliest of `stable_at`, `escalated_at` and `closed_at`, and the fix made it the latest. For a case escalated and later marked stable or closed, participant time kept accruing across the gap, and the cost jumped when the later event landed. Case 5363 is the example: flat at 2261 from Sep 5 to Sep 9, then 6241 when marked Stable.

**Deploy:** Image `main-65f7df6e` ran its database upgrade on Sep 2 at 18:14Z and replaced the scheduler pods at 18:15Z. That is the first deploy containing the commit.

**First inflated cost:** Case 5284 on Sep 3 at the 11:20Z sync, 3331 to 8804. It had been flat since Aug 29 and was marked Stable that day. I found no earlier inflation in the Sep 2–3 diffs. I haven't confirmed the stable timestamp from case data, since the logs don't include it.

**Fix:** The cut-off is back to `min`, with a regression test that fails under `max`. Full suite: the same 8 failures as before, none from this change.

**Second issue (TypeError):** 708 errors from Sep 8 to Sep 14 came from projects with `annual_employee_cost` set to NULL. The project edit form can clear that field, and the update writes the NULL. `get_hourly_rate` now falls back to the model defaults (50000 and 2080), with two tests. Projects that already have NULLs still have them in the database and need a data fix. The same division in `incident_cost` is unguarded and was not changed.

**Caveats:** The `FIRST_INFLATED` and deploy link rest on the cost-sync log. Nothing is committed.

```
FILE: src/dispatch/case_cost/service.py
FUNCTION: get_participant_role_time_seconds
INTRODUCED_BY: 20f33137d520c7472bf9f634b29b730bd83f860e
DEPLOYED_IMAGE: main-65f7df6e
FIRST_INFLATED: 2025-09-03
MISSING_SETTING: annual_employee_cost
```