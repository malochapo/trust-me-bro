Here is how a newly processed signal instance is routed today. I read the code and did not run it.

## Entry point and order

`signal_instance_create_flow` in `signal/flows.py` does the following, in order:

1. It redacts `raw` with `redact_raw`.
2. It extracts entities with `entity_service.find_entities`, using the signal's entity types plus those with scope `all`.
3. It calls `signal_service.filter_signal`, which returns `True` if the instance was snoozed or deduplicated.
4. If `filter_signal` returned `True`, the flow logs the result and returns. If the instance has a `case_id`, the case has a conversation and `_should_update_signal_message` is true, it calls `update_signal_message`. No new case is created.
5. If the instance is `canary`, it returns without creating a case.
6. If `signal.create_case` is false, it returns without creating a case.
7. Otherwise it resolves case type, priority, oncall service and conversation target, then calls `case_service.create` and sets `signal_instance.case`.

`filter_signal` in `signal/service.py` runs the checks in this order:

1. It calls `filter_snooze`.
2. It calls `filter_dedup` only if `filter_action` is still unset, so a snoozed instance is never deduplicated.
3. If `filter_action` is still unset, it sets it to `SignalFilterAction.none`. Otherwise it returns `True`.
4. It commits in both cases.

## Snooze: `filter_snooze`

It iterates `signal_instance.signal.filters` and skips any filter that is not `mode == active` and `action == snooze`.

- **No expiration:** a filter with no `expiration` is skipped with a warning.
- **Expired filter:** if `expiration` (treated as UTC) is at or before now, the code does `break`, not `continue`. The first expired active snooze filter stops evaluation of all remaining filters, so later unexpired snooze filters are not checked.
- **With an expression:** it builds a query on `SignalInstance` for the same `signal_id`. It applies `apply_filter_specific_joins` and `apply_filters` with the filter's `expression`, then restricts the result to `SignalInstance.id == signal_instance.id`. If the instance matches, `filter_action` is set to `snooze` and the loop breaks.
- **Without an expression:** the instance is snoozed regardless of entities or content.

The expression is a JSON filter spec (field, op, value, with and/or nesting) evaluated against the instance and its joins, typically entities and entity types. The only time bound is the filter's `expiration`. There is no lookback window.

## Deduplication: `filter_dedup`

**Canary instances.** If `signal_instance.canary` is true, it returns immediately with no dedup.

**Signal with no filters at all.** This is a default rule that ignores entities. It looks for the most recent instance (`created_at` descending) with all of these properties:

- the same `signal_id`;
- `created_at >= now - SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES * 60` seconds;
- a different id;
- `case_id` not null;
- not canary.

If it finds one, the instance takes that `case_id` and `filter_action` becomes `deduplicate`. The default is **45 minutes**, from `config.SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`, and it can be set by an environment variable. The `filter_signal` docstring says "1-hour window", but the code uses 45 minutes unless overridden.

**Signal with any filters.** The default rule is skipped entirely. This includes signals whose only filters are snooze filters or inactive filters. It iterates the filters, skipping any that are not `active` or not `deduplicate`. For each remaining one:

- It starts from instances of the same signal that are not canary.
- It joins entities and entity types, then applies the filter's `expression`.
- It keeps instances with `created_at >= now - f.window` seconds. `SignalFilter.window` is in seconds. The DB column default is 3600 (1 hour), but the pydantic model default at `models.py:282` is 600 (10 minutes), so filters created through the API schema without a window get 600.
- It requires a shared entity: instances must have an entity whose id is in the current instance's entity ids. If the current instance has no entities, the `IN` list is empty and nothing matches.
- It excludes the instance itself and orders by `created_at` ascending. The earliest match wins.

If any instance matches, the current instance takes `instances[0].case_id` and `filter_action` becomes `deduplicate`, then the loop breaks. This branch does not require the matched instance's `case_id` to be non-null, unlike the default branch. A match with no case would therefore set `case_id` to `None` while still marking the instance as deduplicated.

## Canary signals

- Snoozing still applies to them, because `filter_snooze` has no canary check.
- `filter_dedup` returns early for them. Both dedup queries also exclude canary instances with `~SignalInstance.canary`, so a canary can never be the target of deduplication.
- If a canary is not snoozed, `filter_action` becomes `none` and the flow returns at the canary check. The instance is stored, but no case is created and no case is attached.

## Resulting outcomes

- **Snoozed:** an active snooze filter has not expired and matches, so `filter_action` is `snooze`, there is no case, and the flow returns.
- **Deduplicated:** `filter_action` is `deduplicate` and the instance is attached to an existing case. The flow returns, and the signal message in Slack may be updated.
- **New case:** the instance is not canary, `create_case` is true, and there was no snooze or dedup match. `filter_action` is `none`.