Here is what the code does today. It comes from `signal/service.py`, `signal/flows.py`, `signal/models.py` and `config.py`.

## Entry point and order

`signal_instance_create_flow` in `signal/flows.py` is called from `process_signal_batch` and from `cli.py`. It runs these steps in order:

1. It loads the instance and redacts `raw` with `redact_raw`.
2. It extracts entities from the instance with `entity_service.find_entities`. It uses the signal's own entity types plus all entity types with `EntityScopeEnum.all`. The result is stored on `signal_instance.entities` and committed.
3. It calls `signal_service.filter_signal`. If that returns True, the flow logs the result, updates the Slack signal message when the instance has a case with a conversation and `_should_update_signal_message` allows it, and returns. No new case is created.
4. If the instance is a canary, it returns without further action.
5. If `signal.create_case` is false, it returns.
6. Otherwise it resolves case type, priority, oncall service and conversation target, creates the case with `case_service.create`, and sets `signal_instance.case`. It then runs `case_flows.case_new_create_flow`, `engage_signal_identity` (only if the signal has engagements and entities were found) and any signal workflows.

## `filter_signal`

`filter_signal` makes two checks in order:

1. It always calls `filter_snooze`.
2. It calls `filter_dedup` only if `filter_action` is still unset after the snooze check.
3. If `filter_action` is still unset, it sets it to `SignalFilterAction.none` and returns False. Otherwise it returns True.
4. It commits the session before returning.

## `filter_snooze`

- It loops over `signal.filters` and skips any filter that is not `mode == active` with `action == snooze`.
- A filter with no `expiration` is logged as a warning and skipped.
- For a filter whose expiration has passed, the code hits `break`, not `continue`. The comparison uses `expiration` as UTC, and `<=` counts as expired. This stops the loop, so no later snooze filter is checked. Since filters are only iterated in relationship order, an expired filter can mask unexpired ones after it.
- If the filter has an `expression`, the code builds a query on `SignalInstance` for the same `signal_id`. It applies `apply_filter_specific_joins` and `apply_filters` with the expression, then restricts the query to `SignalInstance.id == this instance`. If the instance matches, `filter_action` is set to `snooze` and the loop breaks.
- An empty expression matches every instance of that signal. The expression is evaluated against the instance's own attributes and entities, so no lookback time window is used for snoozing.
- A snoozed instance does not get a case. Nothing else is done with it here.

## `filter_dedup`

- **Canary signals** return immediately. They are never deduplicated.
- **No filters on the signal at all** (`signal.filters` is empty):
  - The code looks for the most recent instance (`created_at` descending) of the same signal.
  - That instance must have been created within `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES * 60` seconds. The setting is read from the environment, is an int, and defaults to **45 minutes**.
  - It must not be this instance, must have a non-null `case_id`, and must not be a canary.
  - On a match, the instance takes that `case_id` and gets `filter_action = deduplicate`. Entities are not considered.
  - The docstring of `filter_signal` says the default is a one-hour window. The code uses 45 minutes by default.
- **Signal has filters:**
  - The code loops over filters with `mode == active` and `action == deduplicate`.
  - Note that if the signal has only snooze filters, `signal.filters` is non-empty. The default-window branch is skipped and no dedup runs at all.
  - Each matching query selects instances of the same signal that are not canaries. It joins entities and entity types, then applies the filter expression with `apply_filters`.
  - The window is `SignalFilter.window`, stored in **seconds**. `_window_start(f.window)` gives now minus that many seconds. The column default is `60*60` (1 hour), while the pydantic schema default in `models.py` is `600` (10 minutes). Filters created through the API therefore get 600 seconds unless the caller sets a value.
  - Candidates must share at least one entity id with the current instance, and must not be the current instance.
  - Candidates are ordered by `created_at` ascending. The earliest one is taken, and the current instance gets its `case_id` and `filter_action = deduplicate`. The first matching filter wins and the loop breaks.
  - There is no `case_id IS NOT NULL` check in this branch. If the earliest match has no case, the instance's `case_id` is set to None while still marked `deduplicate`. It is then treated as filtered and no case is created.
  - There is no `expiration` check for dedup filters.

## Canary signals

- They can be snoozed, because `filter_snooze` has no canary check.
- They are never deduplicated, and they are excluded as candidates when other instances are deduplicated.
- If a canary is not snoozed, `filter_signal` sets its action to `none`. The flow then returns at the canary check, so no case, workflows or engagement are created. The instance is only stored.

## Outcomes

- **Snoozed:** `filter_action = snooze` and no case is created.
- **Deduplicated:** `filter_action = deduplicate`, `case_id` is set to an existing case and the signal message is updated. No new case is created.
- **New case:** `filter_action = none`, the instance is not a canary and `create_case` is true, so a case is created.