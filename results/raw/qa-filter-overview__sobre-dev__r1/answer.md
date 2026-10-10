Everything below comes from `src/dispatch/signal/service.py` and `flows.py`. I read the code but did not run it.

## Order of checks

`signal_instance_create_flow` in `flows.py` runs these steps:

1. It redacts `raw` with `redact_raw`, then extracts entities from the signal's entity types plus all `scope=all` entity types. It stores them on the instance.
2. It calls `signal_service.filter_signal`, which does the following:
   - It calls `filter_snooze`.
   - It calls `filter_dedup` only if `filter_action` is still unset after the snooze step.
   - If `filter_action` is still unset after both, it sets it to `SignalFilterAction.none`. Otherwise it returns `filtered=True`. It commits either way.
3. If `filter_signal` returned True (snoozed or deduplicated):
   - The flow logs and returns.
   - If the instance has a `case_id` and that case has a conversation, `_should_update_signal_message` is checked. If it passes, `update_signal_message` runs.
   - No case is created and no workflows run.
4. If the instance is a canary, the flow returns without creating a case.
5. If `signal.create_case` is false, the flow returns without creating a case.
6. Otherwise it resolves the case type, priority, oncall service and conversation target. For each one it prefers the instance value, then the signal value, then the case type value (priority and case type have no case-type fallback). It then creates the case with `case_service.create` and sets `signal_instance.case`. It runs `case_new_create_flow` with `create_all_resources=False`. If the signal has engagements and entities, it runs `engage_signal_identity`. Finally it runs each of the signal's workflows.

## Snooze (`filter_snooze`)

It loops over `signal_instance.signal.filters`.

- **Skipped filters:** it skips any filter that is not `mode == active` or not `action == snooze`.
- **No expiration:** a filter with no `expiration` logs a warning and is skipped. A snooze filter therefore only works with an expiration.
- **Expired filter:** if `expiration` (treated as UTC) is at or before now, the code runs `break`, not `continue`. The loop stops, so any later snooze filters on that signal are not evaluated.
- **Match, with an expression:** it builds a query over `SignalInstance` for the same `signal_id`. It applies `apply_filter_specific_joins` and `apply_filters` with the filter's `expression`, then restricts to `SignalInstance.id == this instance`. If a row comes back, `filter_action` is set to `snooze` and the loop breaks.
- **Match, no expression:** an empty expression snoozes every instance of the signal.
- **Filter content:** the expression is a list of filter specs, evaluated by `apply_filters` against the instance and its joined entities.
- **Time window:** the only time value is the absolute `expiration`. `SignalFilter.window` is not used for snoozing.
- **Canaries:** `filter_snooze` has no canary check, so a canary can be snoozed.

## Deduplication (`filter_dedup`)

- **Canaries:** a canary returns immediately with no dedup. Canary instances are also excluded from the candidate set (`~SignalInstance.canary`) in both branches below.

**Branch 1: the signal has no filters at all.**
- The default window is `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES * 60` seconds, passed through `_window_start(seconds)`.
- That setting is in `config.py`. It is an int in minutes and defaults to 45, configurable by env var.
- The `filter_signal` docstring says "1-hour window". The code uses 45 minutes.
- The match is any other instance of the same signal, created at or after the window start, that has a non-null `case_id` and is not a canary. There is no entity matching.
- It takes the most recent such instance (ordered by `created_at` descending). It copies that instance's `case_id` and sets `filter_action = deduplicate`.

**Branch 2: the signal has at least one filter of any kind.**
- A snooze-only filter, an inactive filter or an expired filter all count. In every case the default dedup is skipped.
- It loops over filters that are `active` and have `action == deduplicate`.
- For each one it queries instances of the same signal that are not canaries. It joins entities and entity types, then applies the filter's `expression` with `apply_filters`.
- It requires `created_at >= _window_start(f.window)`. `f.window` is in seconds. The DB column default is 3600 (1 hour). The Pydantic `SignalFilterBase` default is 600 (10 minutes). Which one applies depends on how the filter was created.
- It requires that the candidate share at least one entity ID with the current instance. It excludes the current instance itself.
- If the current instance has no entities, the `IN ()` list is empty and nothing matches.
- It orders by `created_at` ascending and takes the earliest instance. It sets `case_id` to that instance's `case_id` and `filter_action = deduplicate`, then breaks.
- Unlike branch 1, this branch does not require the candidate's `case_id` to be non-null. A match whose `case_id` is None still marks the instance as deduplicated, with no case attached.
- If no filter matches, nothing is set and the flow can go on to create a case.

## Canary behaviour

1. A canary can still be snoozed.
2. It is never deduplicated, and it is never used as a dedup target.
3. If it is not snoozed, `filter_action` ends up as `none`. `signal_instance_create_flow` then reaches the canary check and returns. The instance is stored, with no case, no engagement and no workflows (the flow's own comment calls this "limited support").