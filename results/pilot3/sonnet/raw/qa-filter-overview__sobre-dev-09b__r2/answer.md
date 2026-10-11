## Order of checks

`signal_instance_create_flow` in `signal/flows.py` runs these steps:

1. It redacts `raw` with `redact_raw`.
2. It extracts entities with `entity_service.find_entities`. The entity types are the signal's own plus those with scope `all`.
3. It calls `signal_service.filter_signal` (`signal/service.py`), which runs the snooze check first, then the dedup check.
4. If `filter_signal` returned True, the flow logs the filter action and returns. If the instance has a case with a conversation, it first calls `update_signal_message` (when `_should_update_signal_message` allows it).
5. If the instance is a canary, the flow returns, so no case is created.
6. If `signal.create_case` is false, the flow returns, so no case is created.
7. Otherwise it creates a case with `case_service.create`, sets `signal_instance.case`, runs `case_new_create_flow`, and then runs engagements and workflows.

## `filter_signal`

- It calls `filter_snooze` first.
- It calls `filter_dedup` only if `filter_action` is still unset after that.
- If neither sets an action, it sets `filter_action = SignalFilterAction.none`. Otherwise it returns True.
- It commits either way.

## Snooze: `filter_snooze`

- **Which filters it considers:** it loops over `signal_instance.signal.filters`. It skips any filter whose mode isn't `active` or whose action isn't `snooze`.
- **Filters without an expiration:** these are logged with a warning and skipped.
- **Expired filters:** if `expiration` (treated as UTC) is less than or equal to now, the code runs `break`, not `continue`. That ends the loop, so later filters in the list are not checked.
- **What a filter matches on:**
  - It builds a `SignalInstance` query for the same `signal_id`, applies `apply_filter_specific_joins` and `apply_filters` using the filter's `expression`, and requires `SignalInstance.id` to equal the current instance.
  - The expression therefore matches on the instance's own fields and entities.
  - If the expression is empty, the instance is snoozed regardless of its content.
- **On a match:** it sets `filter_action = snooze` and breaks. No case is created or linked.
- **Time window:** the only time value is the absolute `expiration`. There is no lookback window.

## Dedup: `filter_dedup`

- **Canary instances:** it returns immediately for these, so they are never deduplicated.
- **Signal has no filters at all:**
  - This is a default rule that ignores entities.
  - It looks for the most recent other instance of the same signal with `created_at >= now - SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES * 60` seconds and a non-null `case_id`. It excludes canary instances and the current instance.
  - `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` is read from the environment in `config.py` and defaults to 45. The `filter_signal` docstring says 1 hour, but the code uses 45 minutes.
  - On a match it copies that `case_id` onto the instance and sets `filter_action = deduplicate`.
- **Signal has filters, so no default rule:**
  - A signal with only snooze filters, or only inactive ones, gets no deduplication at all, because the default branch runs only when the filter list is empty.
  - Each filter with mode `active` and action `deduplicate` is tried in list order, and the first match wins.
  - The query is: same signal, non-canary, joined to entities and entity types, with the filter's `expression` applied by `apply_filters`.
  - The matched instance must share at least one entity ID with the current instance, must have `created_at >= now - f.window` seconds, and must not be the current instance.
  - The results are ordered by `created_at` ascending. The code takes `instances[0].case_id`, the earliest match, and sets `deduplicate`.
  - It does not require the matched instance's `case_id` to be non-null, unlike the default branch. If the earliest match has no case, the new instance gets `case_id = None` yet is still marked `deduplicate`.
- **Window units:** `SignalFilter.window` is stored in seconds. The DB column default is 3600 (1 hour). The pydantic `SignalFilterBase.window` defaults to 600 (10 minutes) when created through the schema.
- **Helper:** `_window_start(seconds)` returns now (UTC) minus that many seconds.

## Canary signals

- `filter_snooze` has no canary check, so a canary instance can be snoozed.
- `filter_dedup` returns early for a canary, and other instances' dedup queries exclude canaries (`~SignalInstance.canary`). Canaries are neither deduplicated nor used as dedup targets.
- If a canary isn't snoozed, `filter_signal` sets its action to `none` and returns False. The flow then returns early, so the instance is stored without a case, conversation, engagement or workflows.

I read the code only. I did not run it.