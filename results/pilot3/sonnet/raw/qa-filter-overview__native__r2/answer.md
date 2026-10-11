Dispatch decides this in `signal_instance_create_flow` (`signal/flows.py`), which calls `filter_signal` (`signal/service.py`). I read the code and did not run it.

## Order of checks

1. `signal_instance_create_flow` first redacts `raw` with `redact_raw`. It then extracts entities with `entity_service.find_entities` and commits them. The entity types are the signal's own plus all types whose scope is `all`.
2. It then calls `signal_service.filter_signal`.
3. `filter_signal` calls `filter_snooze` first.
4. `filter_dedup` runs only if `filter_action` is still unset after the snooze check.
5. If neither check set an action, `filter_action` becomes `SignalFilterAction.none` and `filter_signal` returns `False`. Otherwise it returns `True`. It commits either way.
6. If `filter_signal` returned `True`, the flow returns early. No case is created and no workflows run. If the instance has a `case_id`, the case has a conversation, and `_should_update_signal_message` allows it, the flow calls `update_signal_message`. In practice that covers the deduplicated case.
7. If the instance is not filtered, the flow returns early when `signal_instance.canary` is set.
8. It also returns early when `signal.create_case` is false.
9. Otherwise it resolves case type, priority, oncall service and conversation target. The signal instance's own value wins, then the signal's, then the case type's. The oncall service is resolved to an assignee.
10. It then creates the case with `case_service.create` and links it to the instance. It runs `case_flows.case_new_create_flow`, `engage_signal_identity` if the signal has engagements and entities were found, and any signal workflows.

## Snooze (`filter_snooze`)

- It loops over `signal.filters`. It considers only filters with `mode == active` and `action == snooze`.
- A filter with no `expiration` is logged as a warning and skipped.
- If `expiration` (treated as UTC) is at or before now, the code does a `break`. This stops the whole loop, not just that filter, so snooze filters later in the list are never checked. Filter order therefore matters.
- If the filter has an `expression`, it builds a query on `SignalInstance` for the same `signal_id`. It applies the filter's joins and `apply_filters`, then restricts the query to this instance's id. If the instance matches, `filter_action` becomes `snooze` and the loop stops.
- If the filter has no `expression`, the instance is snoozed unconditionally.
- Snooze matches on the instance's own data, such as entities and fields, through the expression. `filter_snooze` has no time window. The only time element is the filter's `expiration`, an absolute datetime.
- A snoozed instance gets no `case_id`.

## Deduplication (`filter_dedup`)

- **Canary:** it returns immediately for a canary instance, so canaries are never deduplicated.
- **No filters on the signal at all** (`not signal.filters`):
  - It uses the default rule, a lookback of `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES * 60` seconds. That setting defaults to **45 minutes** in `config.py` and can be overridden by environment variable.
  - It looks for another instance of the same signal that is not this one, has a non-null `case_id`, is not a canary, and has `created_at` within the window.
  - It takes the most recent such instance (`order_by created_at desc`).
  - It copies that instance's `case_id` and sets `deduplicate`.
  - It does not look at entities.
  - The `filter_signal` docstring says "1-hour window", but the code uses 45 minutes by default.
- **Filters exist** (even if they are all snooze filters or inactive):
  - The default rule is skipped entirely.
  - It loops over filters with `mode == active` and `action == deduplicate`.
  - For each one it queries instances of the same signal that are not canaries. It joins entities and entity types and applies the filter's `expression`. It requires `created_at >= now - f.window` seconds and excludes the current instance.
  - It also requires an overlap in entities: the other instance must share at least one entity id with the current instance's entities.
  - It takes the earliest match (`order_by created_at asc`) and copies its `case_id`.
  - On the first filter that matches, it sets `deduplicate` and stops.
  - The query joins on entities, so an instance with no entities cannot match a filter-based dedup.
  - `f.window` is in **seconds**. The column default is 3600, so 1 hour. The Pydantic model field `window` defaults to 600, so 10 minutes.
- Unlike the default rule, the filter path does not require the matched instance to have a `case_id`. If the earliest match has none, `case_id` is set to `None` but `filter_action` is still `deduplicate`.

## Canary signals

- They are still checked for snooze. `filter_snooze` has no canary guard, so a canary can be snoozed.
- Dedup skips them. Other instances' dedup queries also exclude canary instances with `~SignalInstance.canary`. A canary therefore never joins a case and never becomes the target of a dedup.
- If a canary is not snoozed, the flow stores the instance (with `filter_action = none`) and returns before any case, engagement or workflow logic.

## Units summary

| Setting | Unit | Value |
|---|---|---|
| `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` | minutes, converted to seconds in code | 45 |
| `SignalFilter.window` (DB column default) | seconds | 3600 |
| `SignalFilterBase.window` (Pydantic default) | seconds | 600 |
| `SignalFilter.expiration` | absolute datetime, UTC | none |