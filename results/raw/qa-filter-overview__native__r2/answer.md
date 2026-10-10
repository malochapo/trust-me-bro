## Entry point

`process_organization_signals` (`signal/flows.py`) fetches up to 500 instances via `get_unprocessed_signal_instance_ids`. These are instances with `filter_action IS NULL` and `case_id IS NULL`, oldest first. It runs them in batches through `process_signal_batch`, which calls `signal_instance_create_flow`. The API path calls `signal_instance_create_flow` directly.

## Order of checks in `signal_instance_create_flow`

1. The flow redacts `raw` with `redact_raw`. It then extracts entities, using the signal's entity types plus the `scope=all` entity types, and stores them on the instance.
2. It calls `signal_service.filter_signal`, which runs the checks below in order.
   - `filter_snooze` runs first.
   - `filter_dedup` runs only if `filter_action` is still unset after the snooze check.
   - If nothing set `filter_action`, `filter_signal` sets it to `none` and returns `False`. Otherwise it returns `True`. It commits either way.
3. If `filter_signal` returned `True`, the flow logs the result. If the instance has a `case_id` and that case has a conversation, and `_should_update_signal_message` allows it, it calls `update_signal_message`. The flow then returns without creating a case. Snoozed and deduplicated instances both exit here.
4. If the instance is a canary, the flow returns. It stores the instance and does nothing else.
5. If `signal.create_case` is false, the flow returns.
6. Otherwise the flow resolves the case type, priority, oncall service and conversation target. For each of these, the instance's own value wins over the signal's, and for oncall service and conversation target the case type is the last fallback. It then calls `case_service.create`, sets `signal_instance.case`, and runs `case_flows.case_new_create_flow`. If the signal has engagements and entities were found, it calls `engage_signal_identity`. It then runs the signal's workflows.

## Snooze: `filter_snooze`

- It loops over `signal.filters`. It skips any filter whose mode is not `active` or whose action is not `snooze`.
- A snooze filter with no `expiration` is skipped with a warning.
- If `expiration` is at or before now (compared as UTC), the code hits `break`, not `continue`. That ends the loop, so any later snooze filters are not checked either.
- If the filter has an `expression`, it builds a query on `SignalInstance` for the same `signal_id`. It applies the filter's joins and `apply_filters(expression)`, and then restricts the query to this instance's `id`. The expression therefore matches on this instance's own attributes, such as entities and entity types. If the query returns the instance, it sets `filter_action = snooze` and breaks.
- If the filter has no expression, it snoozes every instance of the signal.
- The snooze check has no time window and does not look at other instances. The only time value is the absolute `expiration` datetime.
- Canary instances are not exempt from snoozing. Nothing in `filter_snooze` checks `canary`.

## Deduplication: `filter_dedup`

- **Canary:** if `signal_instance.canary` is true, it returns immediately and no deduplication happens.
- **Signal has no filters at all:** the default rule applies.
  - Window: `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`, which defaults to 45 and is converted to seconds (`* 60`) for `_window_start`.
  - It looks for the newest instance of the same signal, ordered by `created_at` descending. That instance must be inside the window, have a different id, have a non-null `case_id`, and not be a canary.
  - If it finds one, it copies that `case_id` onto this instance and sets `filter_action = deduplicate`.
  - It does not look at entities or at any expression.
- **Signal has filters:** the loop considers only filters that are `active` and have action `deduplicate`. The default 45-minute rule does not run in this branch, even if none of the filters are dedup filters. A signal with only snooze filters therefore gets no deduplication.
  - For each filter, it queries instances of the same signal that are not canaries. It joins entities and entity types and applies `apply_filters(f.expression)`.
  - It requires `created_at` to be within `f.window` seconds before now. `SignalFilter.window` is an integer in seconds. The column default is 3600 (1 hour). The Pydantic create model defaults to 600 (10 minutes), so filters created through the API get 600 unless a value is sent.
  - It requires the candidate to share at least one entity id with this instance (`Entity.id IN` this instance's entity ids), and requires a different id.
  - It takes the earliest match by `created_at` ascending. It copies `instances[0].case_id` onto this instance, sets `filter_action = deduplicate`, and stops at the first filter that matches.
  - This branch does not require the candidate's `case_id` to be non-null. A matching earlier instance that has no case would set this instance's `case_id` to `None`, while `filter_action` is still `deduplicate`.
  - An instance with no entities matches nothing here, because of the entity-id restriction and the inner joins.

## Canary signals

- Canary instances can be snoozed.
- They are never deduplicated into an existing case.
- They are never used as a deduplication target. Both dedup queries exclude `canary` rows.
- If they are not snoozed, `signal_instance_create_flow` returns after `filter_signal` without creating a case or running workflows or engagements. The instance is stored with `filter_action = none` and no case.

## Units summary

| Item | Unit | Default |
|---|---|---|
| Snooze `expiration` | absolute datetime, UTC | none; a filter without one is ignored |
| Default dedup window (`SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`) | minutes, converted to seconds in code | 45 |
| `SignalFilter.window` | seconds | 3600 in the DB column, 600 in the Pydantic model |

The `filter_signal` docstring says the default dedup window is 1 hour. The code uses the 45-minute config value.