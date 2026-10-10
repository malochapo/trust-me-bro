Everything below is from the code as it stands. The entry point is `signal_instance_create_flow` in `signal/flows.py`, which `process_signal_batch` calls for each unprocessed instance. The batch loop commits after each instance and rolls back if one raises.

## Order of checks in `signal_instance_create_flow`

1. **Load and redact.** It loads the instance and runs `redact_raw` on `raw`.
2. **Entity extraction.** It gathers the signal's entity types plus all entity types with scope `all`. If any exist, `entity_service.find_entities` runs and the result is stored in `signal_instance.entities`.
3. **`signal_service.filter_signal`** (`signal/service.py`). It runs two steps in order:
   - `filter_snooze` runs first.
   - `filter_dedup` runs only if `filter_action` is still unset after snoozing.
   - If neither step set an action, `filter_action` is set to `none` and `filter_signal` returns `False`. Otherwise it returns `True`.
   - It commits either way.
4. **If `filter_signal` returned True (snoozed or deduplicated).**
   - If the instance has a `case_id`, that case has a conversation, and `_should_update_signal_message` agrees, `update_signal_message` runs.
   - The flow then returns. No case is created and no workflows run.
   - A snoozed instance has no `case_id`, because `filter_snooze` never sets one. So it is only logged and stored.
5. **Canary check.** If `signal_instance.canary` is true, the flow returns. The instance is stored and nothing more happens.
6. **`signal.create_case` check.** If it is false, the flow returns.
7. **Case creation.** Otherwise the flow does the following:
   - It resolves case type, priority, oncall service and conversation target. The instance's value wins, then the signal's, then the case type's. Priority has no case-type fallback.
   - It calls `case_service.create`, which creates the case. `case_flows.case_new_create_flow` then runs with `create_all_resources=False`.
   - It runs `engage_signal_identity` if the signal has engagements and there are entities.
   - It runs each of the signal's workflows through `signal_workflow_run_flow`.

## Snooze: `filter_snooze`

- It loops over `signal_instance.signal.filters`. Only filters with mode `active` and action `snooze` are considered.
- A filter with no `expiration` is logged as a warning and skipped.
- If a filter's `expiration` (compared as UTC) is at or before now, the code does `break`, not `continue`. That ends the whole loop, so any later snooze filters in the list are not evaluated.
- If the filter has an `expression`, the code builds a query over `SignalInstance` for the same `signal_id`. It applies `apply_filter_specific_joins` and `apply_filters` with the expression, then restricts to this instance's `id`. If a row comes back, the instance gets action `snooze` and the loop breaks.
- If the filter has no `expression`, the instance is snoozed regardless of its content.
- Matching is whatever the expression says. It is a filter spec over `SignalInstance` columns and joined models such as `Entity` and `EntityType`. It is not limited to entities.
- Snoozing uses no time window. Only `expiration` matters.

## Deduplication: `filter_dedup`

**Canary instances skip it.** A canary instance returns immediately, unchanged. This is checked at the top.

**No filters at all on the signal (`not signal.filters`).**
- This is the "default" rule. The check looks at whether the signal has any filters, not whether it has any deduplicate filters.
- It looks for a `SignalInstance` with the same `signal_id`, `created_at` within the last `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES * 60` seconds, a different `id`, a non-null `case_id`, and `canary` false.
- `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` comes from `config.py`. It is cast to `int` and defaults to 45 minutes.
- It takes the most recent match (`ORDER BY created_at DESC`) and copies its `case_id`. The action becomes `deduplicate`.
- Entities are not considered.

**The signal has filters.**
- The code loops over filters with mode `active` and action `deduplicate`. Snooze filters are skipped here.
- For each filter it builds a query on same-`signal_id`, non-canary instances. It joins `entities` and `entity_type`, then applies the filter's `expression`.
- It restricts `created_at` to within the last `f.window` seconds. `SignalFilter.window` is an integer column in seconds. The column default and the pydantic default are not the same, as shown below.
- It joins `entities` a second time and requires that the entity id be in the current instance's entity ids. It also excludes the current instance.
- It orders by `created_at` ascending, so the earliest match wins. It then copies `instances[0].case_id` and sets the action to `deduplicate`, and the first filter that matches ends the loop.
- If the signal has filters but none is an active deduplicate filter, no deduplication happens. The 45-minute default rule is not applied in that case.
- The inner joins mean an instance with no entities cannot match a filter, and neither can a candidate with no entities.
- This query does not require `case_id` to be non-null. The earliest matching instance could therefore carry a null `case_id`, which would be copied onto this instance while it is still marked `deduplicate`.

## Windows and units

| Setting | Unit | Default |
|---|---|---|
| Default dedup (signals with no filters) | minutes in config, converted to seconds in code | 45 minutes (`SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`) |
| `SignalFilter.window` | seconds | DB column default is 3600 (1 hour); `SignalFilterBase.window` pydantic default is 600 (10 minutes) |
| Snooze `expiration` | a datetime, treated as UTC | none; a missing value means the filter is skipped |

Windows are computed by `_window_start(seconds)`, which returns now (UTC) minus that many seconds.

## Canary signals

- They are never deduplicated. `filter_dedup` returns early for a canary instance. Other instances' dedup queries also exclude canary instances with `~SignalInstance.canary`.
- Snooze is not skipped for canaries. `filter_snooze` has no canary check, so a canary can be snoozed if a filter matches.
- If a canary is not snoozed, `filter_signal` sets action `none`. The flow then reaches the canary check and returns. The instance is stored, but no case, engagement or workflows are created.

## Wording that doesn't match the code

The `filter_signal` docstring says the default rule groups instances "for a 1-hour window, regardless of the entities". The code actually uses the 45-minute config default, and only when the signal has no filters.