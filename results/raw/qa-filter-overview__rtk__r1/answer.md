Here is how it works today. It's from `src/dispatch/signal/flows.py` and `src/dispatch/signal/service.py`. I read the code but didn't run it.

## Order of checks

`signal_instance_create_flow` (flows.py) runs these steps in order:

1. It redacts `raw` with `redact_raw`.
2. It extracts entities. The entity types come from the signal's own types plus all types with `EntityScopeEnum.all`. The entities are stored on the instance and committed.
3. It calls `signal_service.filter_signal`, which runs the snooze and dedup checks (below).
   - If `filter_signal` returns True, the flow logs the result.
   - If the instance has a case with a conversation, `_should_update_signal_message` is true, and `update_signal_message` runs.
   - The flow then returns without creating a case.
4. If the instance is a canary, the flow returns, so no case is created.
5. If `signal.create_case` is false, the flow returns, so no case is created.
6. Otherwise it resolves the case type, priority, oncall service and conversation target. The instance's value wins, then the signal's, then the case type's (priority has no case-type fallback). It then builds a `CaseCreate` and calls `case_service.create`. The result is set as `signal_instance.case`, and the case flow continues.

## `filter_signal`

`filter_signal` calls `filter_snooze` first. It calls `filter_dedup` only if `filter_action` is still unset. If neither check set an action, it sets `filter_action = SignalFilterAction.none`. It commits and returns True only if snooze or dedup applied.

## `filter_snooze`

- It loops over `signal_instance.signal.filters`.
- It skips filters whose mode isn't `active` or whose action isn't `snooze`.
- It skips (with a warning) any snooze filter that has no `expiration`.
- If the filter's `expiration` (treated as UTC) is at or before now, it does `break`, not `continue`. That stops the loop, so any later snooze filters are not checked.
- If the filter has an expression, it queries `SignalInstance` rows for the same `signal_id`, applies the filter-specific joins and `apply_filters(expression)`, and restricts to the current instance's id. If the instance matches, it sets `filter_action = snooze` and breaks. In practice the match is on the instance's entities and fields as the expression defines them.
- If the filter has no expression, it snoozes every instance of that signal.
- Snooze doesn't check `canary`, so a canary instance can be snoozed.

## `filter_dedup`

- **Canary:** if `signal_instance.canary` is set, it returns immediately, so canaries are never deduplicated.
- **No filters on the signal:** this is the default rule, and it ignores entities.
  - It looks for the newest instance of the same signal where `created_at >= now - SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES * 60 seconds`.
  - That instance must have a non-null `case_id`, be a different instance, and not be a canary.
  - `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` is in minutes, set in config.py, and defaults to 45.
  - If one is found, the instance takes that `case_id` and gets `filter_action = deduplicate`.
- **Signal has filters:** it loops over filters that are `active` and have action `deduplicate`. Snooze filters being present still counts as "has filters", so the default rule is skipped in that case. For each dedup filter it queries the same signal's non-canary instances.
  - It joins entities and entity types and applies `apply_filters(f.expression)`.
  - It requires `created_at >= now - f.window`. `f.window` is in seconds, defaults to 3600 (1 hour) in the DB column, and the Pydantic model default is 600 (10 minutes).
  - It requires the instance to share at least one entity id with the current instance's entities, and excludes the current instance.
  - It takes the earliest match by `created_at` and copies its `case_id`.
  - On a match it sets `deduplicate` and breaks.
  - The query doesn't filter on `case_id` being non-null, so a matching instance with no case gives `case_id = None`, but the action is still `deduplicate`.

## Things the code does that differ from its docstrings

- The `filter_signal` docstring says the default rule is a 1-hour window. The code uses the 45-minute config default.
- The default rule picks the newest matching instance. The filter rule picks the earliest.
- Dedup filters have no expiration check. Only snooze filters use `expiration`.

## Canary summary

- A canary can be snoozed. That returns True, and the flow stops there.
- A canary is never deduplicated, and canaries are excluded as dedup targets for other instances.
- An unsnoozed canary hits the `if signal_instance.canary: return` in the flow. The instance is stored, but no case or further handling follows.