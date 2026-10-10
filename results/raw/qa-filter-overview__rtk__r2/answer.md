Dispatch decides this in `signal_service.filter_signal` (`signal/service.py`). `signal_instance_create_flow` (`signal/flows.py`) calls it after redaction and entity extraction. I read the code but did not run it.

## Order of checks in `signal_instance_create_flow`

1. `redact_raw` masks the payload. `entity_service.find_entities` then attaches entities, using the signal's entity types plus all entity types with scope `all`.
2. `signal_service.filter_signal` runs. It calls `filter_snooze` first.
3. `filter_dedup` runs only if `filter_action` is still unset after the snooze check.
4. If neither set an action, `filter_action` becomes `SignalFilterAction.none`, and `filter_signal` returns False. If an action was set, it returns True. It commits either way.
5. If `filter_signal` returned True, the flow returns early. It creates no case and runs no workflows. If the instance has a `case_id` and the case has a conversation, and `_should_update_signal_message` allows it, it calls `update_signal_message`.
6. If `signal_instance.canary` is set, the flow returns.
7. If `signal.create_case` is false, the flow returns.
8. Otherwise it resolves case type, priority, oncall service and conversation target. Each takes the instance value first, then the signal's, then the case type's (priority has no case-type fallback). It calls `case_service.create` and `case_flows.case_new_create_flow`. It then calls `signal_flows.engage_signal_identity` (only if the signal has engagements and `entities` is non-empty) and runs each of the signal's workflows with `workflow_flows.signal_workflow_run_flow`.

## Snooze: `filter_snooze`

It loops over `signal.filters` and skips any filter that is not `mode == active` with `action == snooze`. For each remaining filter:
- **No `expiration`:** it logs a warning and skips the filter. A snooze without an expiration never applies.
- **Expired:** if `expiration` is at or before the current UTC time, it does `break`, not `continue`. The loop stops there, so later snooze filters in the list are not checked. This is order-dependent.
- **Has an expression:** it builds a query on `SignalInstance` for the same `signal_id`, applies `apply_filter_specific_joins` and `apply_filters` with `f.expression`, and restricts it to this instance's id. If the instance comes back, it sets `filter_action = snooze` and stops.
- **Empty expression:** it snoozes every instance of the signal.

Snooze matches on the expression, which is evaluated against the stored instance and its related data such as entities. It does not use `window`. The only time bound is the absolute `expiration` datetime. `expiration` is compared as UTC, because `tzinfo` is forced to UTC on the naive stored value.

Snooze does not check `canary`, so canary instances can be snoozed.

## Deduplication: `filter_dedup`

**Canary:** if `signal_instance.canary` is set, it returns immediately. No dedup happens.

**Signal has no filters at all (the default path):**
- The window is `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES * 60` seconds, via `_window_start`. `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` is in `config.py`, an int read from the environment with a default of 45 minutes.
- It looks for another instance of the same signal, created within that window, with a non-null `case_id`, a different id, and not canary.
- It takes the most recent one (`desc` by `created_at`). It copies that instance's `case_id` onto this instance and sets `filter_action = deduplicate`.
- It does not look at entities.
- The `filter_signal` docstring says "1-hour window", but the code uses 45 minutes by default.

**Signal has filters:**
- The default window above is not used, even if none of the filters is a dedup filter. In that case nothing is deduplicated.
- For each filter that is `active` with `action == deduplicate`, it queries non-canary instances of the same signal. The query joins entities and entity types, applies the filter's expression with `apply_filters`, and requires `created_at >= now - f.window` seconds.
- It also requires that the candidate's entity be one of this instance's own entities (`Entity.id` in this instance's entity ids), and that it is not this instance.
- It orders by `created_at` ascending and takes the earliest match. It copies that match's `case_id` and sets `deduplicate`. It stops at the first filter that matches.
- `SignalFilter.window` is in seconds. The database column defaults to 3600 (1 hour). The pydantic `SignalFilterBase` defaults to 600 (10 minutes), so filters created through the API get 600 unless the caller sets it.
- This path does not require the candidate's `case_id` to be non-null. If the earliest match has no case, the instance is marked `deduplicate` with `case_id = None`.
- If this instance has no entities, `filter_dedup` raises no error. Its entity condition becomes `IN ()` and matches nothing, and the inner join on entities already excludes candidates that have no entities.

## Canary signals

- In `filter_dedup`, a canary instance is never deduplicated. Canary instances are also excluded as dedup targets in both paths.
- A canary instance can still be snoozed. If it is, the flow returns early at the filtered branch.
- If the canary instance is not snoozed, `filter_signal` sets `filter_action = none`. The flow then returns at the canary check, before any case, workflow or engagement is created. The instance is just stored, and `case_id` stays empty.