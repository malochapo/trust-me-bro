Here is how it works in `src/dispatch/signal/`, from reading the code. I didn't run it.

## Order of checks

The entry point is `signal_flows.signal_instance_create_flow` in `flows.py`. The scheduler loop calls it through `process_signal_batch`. `get_unprocessed_signal_instance_ids` picks up instances with no `filter_action` and no `case_id`, oldest first, at most 500 per call.

1. It redacts `raw` with `redact_raw`.
2. It extracts entities for the signal's entity types plus all `scope=all` entity types, and commits them.
3. It calls `signal_service.filter_signal`, which does the following:
   - It calls `filter_snooze`.
   - If that left `filter_action` unset, it calls `filter_dedup`.
   - If `filter_action` is still unset, it sets it to `SignalFilterAction.none`. Otherwise it returns `True` (filtered).
   - It commits.
4. If filtered, the flow logs and, when the instance has a case with a conversation and `_should_update_signal_message` says so, it calls `update_signal_message`. It then returns. No new case is made.
5. If the instance is a canary, the flow returns here.
6. If `signal.create_case` is false, the flow returns.
7. Otherwise it resolves case type, priority, oncall service and conversation target, with priority given to the instance, then the signal, then the case type. It then creates the case with `case_service.create` and runs `case_flows.case_new_create_flow`. It then runs `engage_signal_identity` if the signal has engagements and entities were found, and finally runs the signal's workflows.

## Snooze: `filter_snooze`

It loops over `signal_instance.signal.filters`. A filter is skipped unless its `mode` is active and its `action` is `snooze`.

- **No expiration:** the filter is skipped with a warning. Snooze filters never apply without an `expiration`.
- **Expired filter:** if `expiration` (treated as UTC) is at or before now, the code does `break`. This stops the whole loop, not just that filter, so any later snooze filters on the signal aren't checked.
- **Empty expression:** the instance is snoozed regardless of its entities.
- **Non-empty expression:**
  - The query selects `SignalInstance` rows with the same `signal_id`.
  - It applies `apply_filter_specific_joins` and `apply_filters` with the expression.
  - It restricts to this instance's `id`.
  - The instance is snoozed if that returns a row. In practice the expression is matched against the instance's own fields and entities.
- **Effect of a match:** it sets `filter_action = snooze` and breaks. It doesn't set a `case_id`.

There is no time window on snooze. The only time input is the absolute `expiration` datetime.

## Deduplication: `filter_dedup`

**Canary:** if the instance is a canary, it returns immediately with no dedup.

**Signal has no filters at all (default dedup):**
- It looks for the most recent other instance of the same signal. That instance must have `created_at >= now - SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES * 60` seconds. It must also have a non-null `case_id` and must not be a canary.
- `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` is read from the environment in `config.py` with a default of **45 minutes**.
- Entities are not compared.
- On a match it copies that `case_id` to the instance and sets `filter_action = deduplicate`.
- The `filter_signal` docstring says "1-hour window", but the code uses the 45-minute config value.

**Signal has filters:** the default branch is skipped, even if the only filters are snooze filters or inactive ones. For each filter that is active and has action `deduplicate`:
- The query selects non-canary instances of the same signal.
- It joins entities and entity types, then applies the filter's `expression`.
- It restricts to `created_at >= now - f.window`. `window` is in **seconds**. The DB column default is 3600 (1 hour). The Pydantic model default at `signal/models.py:282` is `600` (10 minutes), so a filter created through the API without a window gets 10 minutes.
- It requires the other instance to share at least one entity id with the current instance's entities.
- It excludes the instance itself and orders by `created_at` ascending.
- On a match, the first (earliest) instance's `case_id` is copied and `filter_action = deduplicate`, then it breaks.
- This query does not require `case_id` to be non-null. If the earliest match has no case, the instance is marked deduplicated with `case_id = None`, and no case is created.
- If the current instance has no entities, the entity-id list is empty and nothing matches.

## Canary signals

- `filter_snooze` has no canary check, so a canary can be snoozed.
- `filter_dedup` returns early for a canary, so it is never deduplicated.
- Canaries are excluded as dedup targets in both branches (`~SignalInstance.canary`).
- If a canary isn't snoozed, `filter_action` ends up `none`. The flow then hits the "limited support for canary signals" return, so the instance is stored but never gets a case, engagement or workflows.

## Outcomes

- **Snoozed:** `filter_action = snooze`, no case.
- **Deduplicated:** `filter_action = deduplicate`, with the matched instance's `case_id`.
- **Neither:** `filter_action = none`. A new case is created only if the instance isn't a canary and `signal.create_case` is true.