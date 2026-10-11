Dispatch decides this in `signal_instance_create_flow` (`signal/flows.py`), which calls `filter_signal` (`signal/service.py`). The scheduler path, `create_signal_instance` in `signal/flows.py`, builds the instance and then uses the same processing. I read that path only as far as its start. Everything below is from the code, and the docstrings and column comments disagree with it in places.

## Order of checks

1. **Entity extraction.** The flow redacts `raw` and extracts entities with `entity_service.find_entities`. The entity types come from the signal's own types plus the types scoped to `all`. The entities are committed before any filter runs.
2. **`filter_signal`** runs the checks in this order:
   - It calls `filter_snooze`.
   - It calls `filter_dedup` only if `filter_action` is still unset after the snooze check.
   - If `filter_action` is still unset, it sets it to `SignalFilterAction.none`. Otherwise it returns `True`.
   - It commits the session in both cases.
3. **If `filter_signal` returned `True`.** The flow logs the action and returns the instance. If the instance has a `case_id`, its case has a conversation, and `_should_update_signal_message` allows it, it calls `update_signal_message` first. No case is created. This also means no workflows run and no engagement happens.
4. **Canary check.** If the instance is a canary, the flow stores it and returns.
5. **`signal.create_case` check.** If it is false, the flow returns without creating a case.
6. **Case creation.** Otherwise the flow resolves these values, with the instance taking priority over the signal, and the signal over the case type:
   - case type
   - priority
   - oncall service
   - conversation target

   It resolves the assignee from the oncall service, calls `case_service.create`, and sets `signal_instance.case`. It then runs `case_flows.case_new_create_flow`, `engage_signal_identity` if the signal has engagements and entities were found, and the signal's workflows.

## Snooze: `filter_snooze`

- It loops over `signal_instance.signal.filters` and skips any filter that is not `mode == active` with `action == snooze`.
- A filter with no `expiration` is skipped with a warning.
- **Expired filters.** If `expiration` (treated as UTC) is at or before now, the code runs `break`, not `continue`. The loop stops at the first expired snooze filter, so any later snooze filters on that signal are never checked.
- **Filter with an expression.** The code builds a query over `SignalInstance` for the same `signal_id`. It applies the filter's JSON expression through `apply_filter_specific_joins` and `apply_filters`, then restricts the query to this instance's `id`. If the instance matches, `filter_action` is set to `snooze` and the loop breaks. The expression runs against the instance and its joined models, not against a time window.
- **Filter without an expression.** The instance is snoozed regardless of entities.
- Snooze uses no lookback window. Only `expiration` matters.
- `filter_snooze` has no canary check. A canary instance can be snoozed.

## Deduplication: `filter_dedup`

- **Canary.** If the instance is a canary, it returns immediately with no deduplication.
- **Signal has no filters at all.** This is the default rule:
  - It looks for the most recent instance, ordered by `created_at` descending.
  - The match must have the same `signal_id`, a different `id`, a non-null `case_id` and `canary` false.
  - It must have been created within `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES * 60` seconds. That config value defaults to **45 minutes** (`config.py`).
  - Entities are ignored.
  - On a match, the instance takes that `case_id` and `filter_action` becomes `deduplicate`.
  - The `filter_signal` docstring says 1 hour, but the code uses 45 minutes.
- **Signal has filters.** The default rule above is skipped entirely, even if none of the filters is a dedup filter. Such a signal never deduplicates unless an active dedup filter matches. For each filter that is active with `action == deduplicate`, in list order:
  - The query covers the same `signal_id` and non-canary instances.
  - It joins entities and entity types.
  - It applies the filter's expression and requires `created_at >= now - f.window` seconds.
  - It restricts matches to instances that share at least one entity (by `Entity.id`) with the new instance.
  - It excludes the new instance itself.
  - It orders by `created_at` ascending and takes the **earliest** match.
  - On a match, the instance takes `instances[0].case_id` and `filter_action` becomes `deduplicate`, then the loop breaks.
- **Window units.** `SignalFilter.window` is stored in seconds. The column default is `60 * 60`, which is 1 hour. The pydantic schema default is `600`, which is 10 minutes. Whichever default applies depends on whether the row was created through the schema or directly through the model.
- **Case ID.** The matched instance's `case_id` is copied without a null check in the filter-based path. An earlier match whose own `case_id` is `None` would copy `None` and still be marked deduplicated.

## Canary signals

- Canary instances skip deduplication.
- Canary instances are excluded as dedup targets in both paths (`~SignalInstance.canary`).
- They are not exempt from snoozing.
- If a canary is not snoozed, it ends up with `filter_action = none`. The flow then reaches the canary check and returns the stored instance. No case is created and no workflows run.