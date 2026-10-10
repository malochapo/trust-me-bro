Everything below comes from `signal/service.py`, `signal/flows.py`, `signal/models.py` and `config.py`. I read the code and did not run it.

## Order of checks

`signal_instance_create_flow` (`signal/flows.py`) handles an instance in this order:

1. It redacts `raw` with `redact_raw`. It then extracts entities with `entity_service.find_entities`, using the signal's entity types plus the `EntityScopeEnum.all` types, and commits them.
2. It calls `signal_service.filter_signal`, which runs the filters:
   - `filter_snooze` runs first.
   - `filter_dedup` runs only if `filter_action` is still unset after the snooze check.
   - If `filter_action` is still unset after both, `filter_signal` sets it to `SignalFilterAction.none` and returns `False`.
   - Otherwise it returns `True`. It commits either way.
3. If `filter_signal` returned `True`, the flow logs the result and returns the instance. If it was deduplicated into a case with a conversation, `_should_update_signal_message` can lead to `update_signal_message`. No case is created.
4. If `signal_instance.canary` is true, the flow returns the instance without creating a case.
5. If `signal.create_case` is false, the flow returns the instance.
6. Otherwise it resolves case type, priority, oncall service and conversation target. Instance values win over signal values, which win over case type values. It then creates the case with `case_service.create`, links it to the instance, and runs `case_flows.case_new_create_flow`. If the signal has engagements and entities were found, it calls `engage_signal_identity`. Finally it runs any signal workflows.

`create_signal_instance` is the scheduler-side entry point. It looks up the signal and raises `DispatchException` if the signal is missing or not enabled. It only creates the instance through `signal_service.create_instance`.

## Snooze: `filter_snooze`

- It loops over `signal_instance.signal.filters`. It skips any filter whose `mode` is not `active` or whose `action` is not `snooze`.
- A snooze filter with no `expiration` is skipped with a warning.
- If the filter's `expiration` (naive datetime, treated as UTC) is at or before now, the code `break`s. It does not `continue`. Filters after the first expired snooze filter are therefore never evaluated, so a later, unexpired snooze filter is ignored.
- If the filter has an `expression`, the code queries `SignalInstance` rows with the same `signal_id`. It applies `apply_filter_specific_joins` and `apply_filters` with the expression, then restricts to `SignalInstance.id == this instance`. If the instance matches, it sets `filter_action = snooze` and stops. The expression is evaluated against the instance's own data, such as entities, and not against earlier instances.
- If the expression is empty, the instance is snoozed regardless of content.
- Snooze does not use `window`. Its only time check is `expiration`.
- A snoozed instance gets no `case_id`.

## Deduplication: `filter_dedup`

**Canary:** if `signal_instance.canary` is true, the function returns immediately, so a canary is never deduplicated.

**Signal has no filters at all** (`signal.filters` is empty):
- The code uses a default rule that ignores entities.
- It looks for the most recent other instance of the same signal where:
  - `created_at >= now - SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES * 60` seconds;
  - `id != this instance`;
  - `case_id` is not null;
  - it is not a canary.
- `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` is read in `config.py` and defaults to **45 minutes**.
- On a match, the instance takes that instance's `case_id` and gets `filter_action = deduplicate`.
- The `filter_signal` docstring says "1-hour window". That is stale: the code uses 45 minutes unless the environment variable is set.

**Signal has filters:**
- Only filters with `mode == active` and `action == deduplicate` are considered.
- A signal with only snooze filters, or only inactive ones, takes this path. The default rule is skipped, so such an instance is never deduplicated and gets a new case.
- For each qualifying filter, the query selects non-canary instances of the same signal. It joins entities and entity types and applies the filter's `expression`.
- It requires `created_at >= now - f.window` seconds. `window` is stored in seconds. The column default is 3600 (1 hour), while the Pydantic `SignalFilterBase.window` default is 600 (10 minutes).
- It requires the matching instance to share at least one entity, by `Entity.id`, with the current instance's entities. An instance with no entities cannot match.
- It excludes the current instance and orders by `created_at` ascending. The earliest match supplies `case_id`. The instance gets `deduplicate` and the loop stops at the first matching filter.
- This path does not require `case_id` to be non-null. The earliest match could have `case_id = None`, in which case the instance is marked `deduplicate` with no case. The default no-filters path does filter on `case_id` being non-null.
- Dedup filters have no expiration check. `expiration` is only used for snooze.

## Canary signals

- A canary is never snoozed or deduplicated by its own checks. `filter_dedup` returns early for it, and the snooze logic has no canary check.
- Canaries are excluded as match targets in both dedup paths (`~SignalInstance.canary`).
- `filter_snooze` has no canary condition, so a matching snooze filter does snooze a canary.
- If a canary isn't snoozed, the flow stores it and returns before case creation. It gets `filter_action = none`, no case, and no workflows or engagement. The code comment calls this "limited support".

## Outcomes

| Outcome | `filter_action` | `case_id` |
|---|---|---|
| Snoozed | `snooze` | unset |
| Deduplicated | `deduplicate` | existing case |
| Not filtered | `none` | new case, if `create_case` is true and it isn't a canary |