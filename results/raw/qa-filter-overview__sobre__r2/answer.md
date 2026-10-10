Dispatch decides this in `signal_instance_create_flow` (`signal/flows.py`), which calls `filter_signal` (`signal/service.py`). I read the code only and ran nothing.

## Order of checks

1. **Entity extraction.** `signal_instance_create_flow` first redacts `raw` and extracts entities with `entity_service.find_entities`. Entities are committed before any filtering.
2. **`filter_signal`.** It calls `filter_snooze` first. It calls `filter_dedup` only if `filter_action` is still unset after that.
   - If `filter_action` is still empty at the end, it is set to `SignalFilterAction.none` and `filter_signal` returns `False`.
   - Otherwise it returns `True`.
   - It commits in both cases.
3. **Filtered (snoozed or deduplicated).** The flow logs the instance and, if the instance has a case with a conversation, may call `update_signal_message`. It then returns without creating a case.
4. **Canary.** If `signal_instance.canary` is set, the flow returns after the filter step. The code comment calls this "limited support". No case is created.
5. **`create_case` disabled.** If `signal.create_case` is false, the flow returns.
6. **New case.** Otherwise it resolves the case type, priority, oncall service and conversation target, with the instance taking precedence over the signal and then the case type. It then builds `CaseCreate` and calls `case_service.create`.

## Snooze (`filter_snooze`)

- It loops over `signal_instance.signal.filters` and skips any filter that is not `mode == active` and `action == snooze`.
- A filter with no `expiration` is logged as a warning and skipped (`continue`).
- If `expiration` (treated as UTC) is at or before now, the code does `break`, not `continue`. The first expired snooze filter in the list therefore stops evaluation of every filter after it.
- If the filter has an `expression`, it queries `SignalInstance` rows for the same `signal_id` and applies `apply_filter_specific_joins` and `apply_filters` with the expression. It snoozes only if the current instance's id is among the results.
- If the expression is empty, it snoozes every instance of that signal.
- On a match it sets `filter_action = snooze` and breaks.
- There is no time window. The only time element is the absolute `expiration` datetime.
- Canary instances are not exempt from snoozing.

## Deduplication (`filter_dedup`)

- **Canary instances return immediately.** They are never deduplicated. Other instances also ignore canary instances as dedup targets (`~SignalInstance.canary`).
- **Signal has no filters at all.** This is the default rule.
  - It looks for the newest other instance of the same signal with `created_at` inside the window and a non-null `case_id`.
  - The window is `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES * 60` seconds. That config value is in minutes, defaults to **45**, and is read from the environment variable of the same name.
  - Entities are not considered.
  - On a match, the instance takes that `case_id` and `filter_action = deduplicate`.
  - The `filter_signal` docstring says "1-hour window", but the code uses 45 minutes by default.
- **Signal has any filters.** The default rule is skipped, even if all the filters are snooze filters. In that case no deduplication happens at all.
  - Only active filters with `action == deduplicate` are used.
  - For each one, it queries the same signal's non-canary instances, joined to entities and entity types, and applies the filter `expression` with `apply_filters`.
  - It restricts to instances created within `f.window` seconds of now.
  - It requires the match to share at least one entity id with the current instance's entities. An instance with no entities therefore never matches.
  - It excludes the current instance and takes the earliest match (`asc(created_at)`).
  - It copies that instance's `case_id` and sets `deduplicate`. The first matching filter wins.
  - This query has no `case_id IS NOT NULL` condition, unlike the default rule. A matched instance with no case would give `case_id = None` while still marking the instance as deduplicated.

## Window defaults

- **`SignalFilter.window` column:** integer seconds, DB default `3600`.
- **`SignalFilterBase` pydantic model:** `window` defaults to `600`, which is 10 minutes. Filters created through the API schema therefore get 600 seconds unless a value is supplied.
- **`SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`:** minutes, default 45. It applies only when the signal has no filters.
- **Snooze `expiration`:** an absolute datetime, not a duration.

## Canary summary

- Canary instances can be snoozed.
- They are never deduplicated and are never used as dedup targets.
- If they are not snoozed, they are stored with `filter_action = none` and never open a case.