I read the signal service, flow and model code and have what I need. This is the full answer.

## Entry points

- `main_processing_loop` in `signal/flows.py` loops over organizations and sleeps 60s (`LOOP_DELAY`) between passes.
- `process_organization_signals` fetches up to 500 instances through `get_unprocessed_signal_instance_ids`. Those are instances with `filter_action IS NULL` and `case_id IS NULL`, oldest first.
- `process_signal_batch` calls `signal_instance_create_flow` for each instance and commits or rolls back per instance.

## Order of checks in `signal_instance_create_flow`

1. It redacts `raw` with `redact_raw`.
2. It extracts entities, using the signal's entity types plus the scope-`all` entity types, via `entity_service.find_entities`. It commits the result.
3. It calls `signal_service.filter_signal`, which runs `filter_snooze`. Only if `filter_action` is still unset does it run `filter_dedup`.
   - If neither sets an action, `filter_action` becomes `none` and `filter_signal` returns `False`.
   - Otherwise it returns `True`. The flow then logs, calls `update_signal_message` if the instance has a case with a conversation and `_should_update_signal_message` allows it, and returns. No case is created.
4. If the instance is `canary`, the flow returns. This check comes after filtering.
5. If `signal.create_case` is false, the flow returns.
6. Otherwise it resolves case type, priority, oncall and conversation target. Instance values take priority over signal values, which take priority over case type values. It then creates the case with `case_service.create`, attaches it to the instance, and continues into `case_new_create_flow`.

## Snooze: `filter_snooze`

It iterates `signal.filters` and skips any filter that is not `mode == active` with `action == snooze`.

- **No expiration:** a filter with no `expiration` is skipped with a warning.
- **Expired filter:** an expired filter (`expiration <= now`, with the naive datetime treated as UTC) hits `break`, not `continue`. Snooze evaluation stops at the first expired snooze filter, and any later filters in the list are never checked. This depends on filter order.
- **With an expression:** the filter runs a query over `SignalInstance` for the same `signal_id`. It applies `apply_filter_specific_joins` and `apply_filters` using `f.expression`, then restricts the query to this instance's id. If that returns a row, the instance gets `filter_action = snooze` and the loop breaks.
- **Without an expression:** the instance is snoozed regardless of its entities.

A snoozed instance gets no `case_id`.

## Dedup: `filter_dedup`

**Canary:** if `signal_instance.canary` is true, it returns immediately with no dedup. Canary instances are also excluded (`~SignalInstance.canary`) from the candidate queries, so they never serve as a dedup target.

**Signal has no filters at all:** this is the default rule.
- It looks for another instance of the same signal with `id != this`, `case_id` not null and `created_at >= now - SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES * 60` seconds. Entities are ignored.
- It takes the most recent one (`desc(created_at)`) and copies its `case_id`.
- It sets `filter_action = deduplicate`.
- `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` is in `dispatch/config.py`. It is an env-configurable int with a default of **45 minutes**.
- The `filter_signal` docstring says a 1-hour window. That is stale, and the code uses 45.

**Signal has filters:** the default rule is not applied, even if none of those filters is an active dedup filter. A signal with only snooze filters therefore never deduplicates. For each filter with `mode == active` and `action == deduplicate`:
- The query is over same-signal, non-canary instances, joined to `entities` and then `entity_type`.
- It applies `apply_filters(query, f.expression)`.
- It requires `created_at >= now - f.window` seconds. `_window_start(seconds)` computes this.
- It joins entities again and requires `Entity.id` to be in this instance's entity ids. At least one entity must be shared.
- It excludes this instance's own id.
- It orders by `created_at` ascending and takes `instances[0].case_id`, so the earliest match wins.
- It sets `deduplicate` and breaks on the first filter that matches.
- The inner joins mean that an instance with no entities, or a candidate with none, cannot match.
- There is no `case_id IS NOT NULL` condition in this branch, so the matched instance's `case_id` can be `None`.

## Window and expiration units and defaults

| Setting | Unit | Default |
|---|---|---|
| `SignalFilter.window` (DB column) | seconds | 3600 (the model comment says 1 hour) |
| `SignalFilterBase.window` (pydantic) | seconds | 600 |
| `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` | minutes, multiplied by 60 | 45 |
| `SignalFilter.expiration` | naive `DateTime`, treated as UTC | none |

The DB column default (3600) and the pydantic default (600) disagree. Which one applies depends on whether the filter is created through the API schema or directly through the model. I did not trace `create_signal_filter` to confirm which path supplies the value.

## Canary signals

- Canary instances are stored with the default `canary=False` unless set otherwise.
- They go through entity extraction and `filter_signal`. `filter_snooze` applies to them like any other instance, so they can be snoozed.
- `filter_dedup` returns early for them, so they are never deduplicated.
- They are never counted as dedup candidates for other instances.
- If not snoozed, they hit the early return in the flow. The instance is stored with `filter_action = none`, no case is created, and nothing further happens.