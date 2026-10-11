Dispatch checks snooze first, then deduplication, then falls through to case creation. The checks are in `src/dispatch/signal/service.py` and `src/dispatch/signal/flows.py`.

## Order of checks

`signal_flows.signal_instance_create_flow` (`flows.py:46`) does the following, in order:

1. It redacts `raw` with `redact_raw`.
2. It extracts entities from the signal's entity types plus the `scope=all` entity types.
3. It calls `signal_service.filter_signal` (`service.py:866`), which runs:
   - `filter_snooze`.
   - `filter_dedup`, only if `filter_snooze` left `filter_action` unset.
   - If `filter_action` is still unset after both, `filter_signal` sets it to `none`.
   - It returns `True` if the instance was snoozed or deduplicated.
4. If `filter_signal` returned `True`, the flow logs the result.
   - If the instance has a `case_id`, and that case has a conversation, and `_should_update_signal_message` allows it, the flow calls `update_signal_message`. A TTLCache with a 60-second TTL and `maxsize=4` backs this check.
   - The flow then returns without creating a case.
5. If the instance is a canary, the flow returns. The comment calls this "limited support".
6. If `signal.create_case` is false, the flow returns.
7. Otherwise it resolves the case type, priority, oncall service, conversation target and severity. Each takes the instance value first, then the signal's, then the case type's.
8. It calls `case_service.create`, sets `signal_instance.case`, and runs `case_flows.case_new_create_flow`.
9. It runs `engage_signal_identity` if the signal has engagements and entities were found.
10. It runs the signal's workflows.

## Snooze (`filter_snooze`, `service.py:743`)

- It loops over `signal.filters` and skips any filter that isn't `mode == active` and `action == snooze`.
- A snooze filter with no `expiration` is logged as a warning and skipped.
- If `expiration`, treated as UTC, is at or before now, the code does `break`, not `continue`. One expired snooze filter therefore stops evaluation of every later filter in the list.
- If the filter has an `expression`, it builds a query over `SignalInstance` for the same `signal_id`. It applies the filter's joins and `apply_filters(query, f.expression)`, then checks whether the current instance's id is in the result. A match sets `filter_action = snooze`.
- If the filter has no `expression`, it snoozes unconditionally.
- Snooze uses an absolute `expiration` datetime. It does not use `window`.
- Snooze does not look at `canary`, so canaries can be snoozed.

## Deduplication (`filter_dedup`, `service.py:789`)

- **Canaries:** `filter_dedup` returns immediately for a canary instance. Canary instances are also excluded (`~SignalInstance.canary`) as dedup targets in both branches below.
- **No filters on the signal:** if `signal.filters` is empty, it applies the default rule.
  - **Matching:** it matches any instance of the same signal, regardless of entities.
  - **Conditions:** the instance must have `created_at >= now - SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES * 60`, a different id, and a non-null `case_id`.
  - **Choice:** it takes the most recent match.
  - **Result:** it copies that `case_id` and sets `deduplicate`.
  - **Window:** `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` is read in `config.py:95` and defaults to 45 minutes.
- **One or more filters, none of them dedup:** if the signal has filters but none are active dedup filters, nothing is deduplicated. The default rule does not run in that case, for example when the signal has only a snooze filter.
- **Active dedup filters:** it loops over the filters and skips any that aren't active or aren't `deduplicate`.
  - **Query:** it takes instances of the same signal, non-canary, joined to entities and entity types. It applies `apply_filters(query, f.expression)`.
  - **Window:** it keeps instances with `created_at >= now - f.window`. `SignalFilter.window` is in seconds. The DB column default is 3600, which is 1 hour. The pydantic model at `models.py:282` defaults to 600, which is 10 minutes.
  - **Entity overlap:** the candidate must share at least one entity with the current instance (`Entity.id in current instance's entity ids`). An instance with no entities can never match.
  - **Choice:** it excludes the instance itself and takes the earliest match (`asc(created_at)`).
  - **Result:** it copies that match's `case_id` and sets `deduplicate`, then stops at the first filter that matches.
  - **Null `case_id`:** unlike the default branch, this branch doesn't require the match to have a `case_id`. If the earliest match has none, the instance is marked `deduplicate` with `case_id = None`.

## Canaries

- Snooze can apply to a canary.
- Dedup is skipped for a canary, and canaries are never used as dedup targets.
- A canary that isn't snoozed gets `filter_action = none`. `signal_instance_create_flow` then stores it and returns before any case, engagement or workflow is created.

## Docstring mismatches

The `filter_signal` docstring says the default dedup window is 1 hour. The code applies 45 minutes through `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`, and 1 hour is only the default for a filter's own `window`.