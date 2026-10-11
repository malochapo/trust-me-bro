For a processed signal instance, Dispatch checks snooze first, then deduplication, and opens a new case only if neither applies. The code is in `src/dispatch/signal/flows.py` and `src/dispatch/signal/service.py`.

## Order of checks

`signal_flows.signal_instance_create_flow` runs these steps in order:

1. It redacts `raw` with `redact_raw`.
2. It extracts entities with `entity_service.find_entities`. The entity types are the signal's own types plus all types with scope `all`.
3. It calls `signal_service.filter_signal`.
   - **Filtered:** if `filter_signal` returns True, the flow logs and, for an instance that has a case with a conversation, calls `update_signal_message` when `_should_update_signal_message` allows it. Then it returns. No case is created.
   - **Not filtered:** the flow continues to the checks below.
4. If `signal_instance.canary` is set, it returns without creating a case.
5. If `signal.create_case` is false, it returns without creating a case.
6. Otherwise it resolves the case type, priority, oncall service and conversation target, then calls `case_service.create` and `case_flows.case_new_create_flow`. After that it runs engagement (`engage_signal_identity`) and any workflows.

Inside `filter_signal`:

- It calls `filter_snooze` first.
- It calls `filter_dedup` only if `filter_action` is still unset.
- If `filter_action` is still unset after both, it sets `SignalFilterAction.none`.
- It commits and returns True only if a snooze or deduplicate action was set.

## Snooze: `filter_snooze`

- It loops over `signal_instance.signal.filters`.
- It skips any filter that isn't `mode == active` with `action == snooze`.
- A filter with no `expiration` is skipped with a warning.
- The filter's `expiration` (a naive `DateTime`) is treated as UTC. If it is at or before now, the code does `break`, not `continue`. The loop stops at the first expired snooze filter, so later snooze filters on that signal are never evaluated.
- If the filter has an `expression`, the code builds a query on `SignalInstance` for this `signal_id`. It adds the entity joins from `apply_filter_specific_joins` and the conditions from `apply_filters`, then restricts to `SignalInstance.id == this instance`. If that returns a row, it sets `filter_action = snooze` and breaks.
- If the filter has no expression, it snoozes every instance of the signal.
- There is no time window and no lookup of earlier instances. The match depends only on this instance's own data and the expiration. Snoozing does not set a `case_id`.
- Canary instances are not exempted from snooze.

## Deduplication: `filter_dedup`

- **Canary:** a canary instance returns immediately, so it is never deduplicated.
- **Signal has no filters at all (default dedup):**
  - The window is `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` (from `config.py`, default 45, env-overridable), converted to seconds and passed to `_window_start`.
  - It looks for another instance of the same signal, with a different id, `created_at >= now - 45 min`, a non-null `case_id`, and `canary` false.
  - It takes the most recent one (`desc(created_at)`).
  - If found, it copies that instance's `case_id` and sets `filter_action = deduplicate`.
  - Entities are ignored.
- **Signal has filters:**
  - The default rule is skipped entirely, even if the signal only has snooze filters. In that case nothing deduplicates.
  - Only filters with `mode == active` and `action == deduplicate` are used, in list order.
  - For each filter, the query selects instances of the same signal that are non-canary, joined through `entities` to `entity_type`.
  - It applies `apply_filters(query, f.expression)` and requires `created_at >= now - f.window`, where `window` is in seconds.
  - It requires a shared entity: `Entity.id` must be among the current instance's entity ids. If the current instance has no entities, nothing matches.
  - It excludes the instance itself and orders by `created_at` ascending.
  - If any rows match, the earliest one's `case_id` is copied and the action becomes `deduplicate`. The loop stops at the first filter that matches.
  - This path has no `case_id IS NOT NULL` condition. The earliest match may have a null `case_id`, which would be copied.
- **Window default for a filter:** the DB column `SignalFilter.window` is an `Integer` in seconds with default 3600 (1 hour). The pydantic base model in `models.py` declares `window: int | None = 600`, so a filter created through the schema without a window gets 600 seconds (10 minutes). Check `models.py` to confirm which create path your filters use.

## Canary signals

- **Snooze:** a canary can still be snoozed.
- **Dedup:** it is never deduplicated, and canaries are excluded as match candidates in both dedup paths.
- **Case creation:** if it isn't snoozed, `signal_instance_create_flow` returns right after filtering, before any case, workflow or engagement. The code comment calls this "limited support", and the instance is just stored.

## Related timing

`_should_update_signal_message` uses a `TTLCache` with a 60-second TTL, keyed by case. It updates the Slack signal message for a deduplicated instance only if the case has a `signal_thread_ts` and at least 5 seconds have passed since the last cached update. The first instance seen for a case returns True without those checks.