Here is how the code decides this today. The entry point is `signal_instance_create_flow` in `signal/flows.py`, which calls `filter_signal` in `signal/service.py`.

## Order of checks

**1. `signal_instance_create_flow(signal_instance_id, ...)`** runs these steps before any filtering:
- It loads the instance and redacts `raw` with `redact_raw`.
- It collects entity types from the signal plus every type with `EntityScopeEnum.all`.
- If there are any, it calls `entity_service.find_entities`, assigns the result to `signal_instance.entities` and commits. Dedup filters depend on this step.

**2. `filter_signal`** then does the following:
- It calls `filter_snooze`.
- It calls `filter_dedup` only if `filter_action` is still unset, so snooze always wins.
- If `filter_action` is still unset, it sets it to `SignalFilterAction.none` and returns `False`. Otherwise it returns `True`.
- It commits in both cases.

**3. Back in the flow**, the result of `filter_signal` is handled like this:
- **Filtered (`True`):** it logs the result and returns the instance. If the instance has a `case_id`, that case has a conversation, and `_should_update_signal_message` allows it, it calls `update_signal_message`. No new case is created.
- **Canary:** `if signal_instance.canary` stores the instance and returns, with no case.
- **`signal.create_case` is false:** it returns without creating a case.
- **Otherwise:** it builds a `CaseCreate`, calls `case_service.create` and sets `signal_instance.case`. It then runs `case_flows.case_new_create_flow`, `engage_signal_identity` (only if the signal has engagements and there are entities), and the signal's workflows.

## Snooze: `filter_snooze`

It loops over `signal_instance.signal.filters` and skips any filter that is not `mode == active` with `action == snooze`.

- **Expiration:** a filter with no `expiration` is logged with a warning and skipped. If the expiration is at or before now (UTC), the code hits `break`, not `continue`. It stops checking all remaining filters, so a later unexpired snooze filter is never evaluated.
- **Matching:** it builds a query on `SignalInstance` for the same `signal_id`, applies `apply_filter_specific_joins` and `apply_filters` with `f.expression`, and restricts it to this instance's `id`. If the instance matches, it sets `filter_action = snooze` and breaks.
- **Empty expression:** the instance is snoozed unconditionally.
- **What the match uses:** whatever fields the expression references. The snooze path doesn't restrict this to entities.
- **Time unit:** the only time value is the absolute `expiration` datetime, a naive column treated as UTC.
- **Case link:** the instance gets no `case_id`.

## Deduplication: `filter_dedup`

- **Canary:** it returns immediately for canary instances, so they are never deduplicated.
- **No filters on the signal at all:** this is the default rule.
  - It looks for another instance of the same signal, regardless of entities.
  - The other instance must have been created within `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES * 60` seconds (via `_window_start`), have a non-null `case_id`, be non-canary and not be this instance.
  - It picks the most recent match, copies its `case_id` and sets `filter_action = deduplicate`.
  - The window comes from the env-configurable setting in `config.py`, default 45 minutes. The `filter_signal` docstring says "1-hour window", which is wrong. The code uses 45 minutes.
- **Signal has filters:** the default rule is skipped entirely, even if none of those filters is a dedup filter. In that case no dedup happens. For each filter that is `active` with `action == deduplicate`, the code does the following:
  - It queries non-canary instances of the same signal and inner-joins `entities` and `entity_type`.
  - It applies `f.expression`.
  - It requires `created_at >= now - f.window` seconds. The `SignalFilter.window` column defaults to 3600 (1 hour), though the Pydantic model's `window` defaults to 600 (10 minutes).
  - It joins entities again and requires the matching instance to share at least one entity id with the current instance's entities. An instance with no entities therefore never matches here.
  - It excludes the instance itself and orders by oldest `created_at`.
  - On the first filter with any match it takes `instances[0].case_id` (the earliest), sets `deduplicate` and breaks.
  - This query does not require `case_id` to be non-null, so the matched instance could have a null `case_id`.
  - `expiration` is not checked for dedup filters.

## Canary signals

- **Dedup:** `filter_dedup` skips them, and both dedup queries also exclude canary instances as match candidates.
- **Snooze:** `filter_snooze` does not look at `canary`, so a canary can be snoozed.
- **Case creation:** a canary that isn't snoozed is stored and returned before any case creation, workflows or engagement. It ends with `filter_action = none`.

I read the code but did not run it.