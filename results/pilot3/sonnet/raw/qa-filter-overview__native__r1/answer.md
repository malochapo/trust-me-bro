Entry point: `signal_instance_create_flow` in `signal/flows.py`. The checks live in `signal/service.py`.

## Order of checks

1. **Preparation.** `signal_instance_create_flow` loads the instance, redacts `raw`, and extracts entities. It uses the signal's entity types plus all entity types with scope `all`, and stores the result in `signal_instance.entities`.
2. **`filter_signal`.** It calls `filter_snooze` first.
3. **Dedup only if not snoozed.** `filter_dedup` is called only if `filter_action` is still unset after the snooze check.
4. **Recording the result.** If neither filter set an action, `filter_signal` sets `filter_action = none`. It then commits and returns `True` only when an action was set (snooze or deduplicate).
5. **Back in the flow.** If `filter_signal` returned `True`, the flow logs the result. If the instance has a case with a conversation, it calls `update_signal_message` when `_should_update_signal_message` allows it. Then it returns. A snoozed instance has no `case_id`, so it never reaches that update.
6. **Canary check.** An instance that passed both filters and is a canary is returned, with no case created.
7. **`create_case` check.** If `signal.create_case` is false, the flow also returns with no case.
8. **Case creation.** Otherwise it resolves case type, priority, oncall and conversation target. Instance values take priority, then signal values, then case type values. It then calls `case_service.create` and sets `signal_instance.case`.

## Snooze (`filter_snooze`)

- It iterates `signal.filters`. It skips any filter whose mode is not `active` or whose action is not `snooze`.
- A filter with no `expiration` is skipped with a warning.
- If `expiration` (treated as UTC) is at or before now, the code hits `break`. This stops the whole loop, so later snooze filters are not evaluated. It does not `continue`.
- With an expression, it builds a query over `SignalInstance` for the same `signal_id` and applies `apply_filter_specific_joins` and `apply_filters(f.expression)`. It then checks whether the current instance's id is in the result. If so, the instance is snoozed and the loop breaks.
- With an empty expression, the instance is snoozed regardless of its content.
- The match is on whatever fields and entities the expression references.
- Snooze has no window. Only the absolute `expiration` timestamp matters.

## Deduplication (`filter_dedup`)

**Canary:** if `signal_instance.canary` is true, it returns immediately with no dedup.

**No filters on the signal at all** (`not signal.filters`). This covers snooze filters too, so any filter of any kind disables this branch.
- Default window: `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` (config default **45 minutes**), converted by `_window_start(minutes * 60)`.
- It finds the most recent other instance of the same signal that has a `case_id`, is not a canary, and was created within the window. It matches on signal only, not on entities.
- If found, it copies that `case_id` and sets the action to `deduplicate`.
- The `filter_signal` docstring says "1-hour window". That is stale. The code uses the 45-minute config value.

**Signal has filters.** It loops over filters that are `active` and have action `deduplicate`.
- The query covers the same signal, non-canary instances, joined through entities and entity types.
- It applies the filter's `expression`. It also requires a shared entity: the other instance must have an entity whose id is in the current instance's entity ids.
- The window is `SignalFilter.window`, which is **seconds**. `_window_start(f.window)` is used as the cutoff. The DB column default is 3600 (1 hour). The Pydantic `SignalFilterBase` default is 600 (10 minutes). Which applies depends on whether the filter was created through the API model or the DB default.
- It excludes the current instance and orders by `created_at` ascending. The earliest match's `case_id` is used, and the first filter that matches wins.
- Two gaps follow from this code:
  - If the signal has filters but none are active dedup filters, no dedup happens. The 45-minute default is not applied.
  - The matching instance's `case_id` isn't checked for null in this branch, so the matched instance can carry a `None` case. In that case the instance is marked `deduplicate` with no case.

## Canary signals

- A canary instance is never deduplicated, and non-canary instances ignore canary instances when looking for matches (`~SignalInstance.canary`).
- `filter_snooze` has no canary check, so a canary can be snoozed.
- If a canary is not snoozed, the flow stores the instance and returns. No case is created and no later steps run. `filter_action` is `none`.