Dispatch decides this in `signal_instance_create_flow` (`signal/flows.py`), which calls `filter_signal` (`signal/service.py`). I read the code only and ran nothing.

## Order of checks

`process_organization_signals` and `process_signal_batch` feed unprocessed instance IDs into `signal_instance_create_flow`. For each instance it does the following:

1. It redacts `raw` with `redact_raw`.
2. It extracts entities with `entity_service.find_entities`. The entity types are the signal's own types plus all types with `EntityScopeEnum.all`. The result is assigned to `signal_instance.entities` and committed.
3. It calls `signal_service.filter_signal`, which runs two checks in order:
   - `filter_snooze` runs first.
   - `filter_dedup` runs only if `filter_snooze` left `filter_action` unset.
   - If neither set an action, `filter_action` becomes `SignalFilterAction.none` and `filter_signal` returns `False`. Otherwise it returns `True`. It commits either way.
4. If `filter_signal` returned `True`, the flow logs and returns the instance without creating a case. If the instance has a `case_id`, the case has a conversation, and `_should_update_signal_message` allows it, it first calls `update_signal_message`. Only deduplicated instances have a `case_id` here.
5. The flow then returns early for a canary instance, and again if `signal.create_case` is false.
6. Otherwise it resolves case type, priority, oncall service and conversation target, with the instance's value taking precedence over the signal's and then the case type's. It then creates the case with `case_service.create`, assigns it to the instance, and runs `case_new_create_flow`, `engage_signal_identity` and the signal's workflows.

## Snooze: `filter_snooze`

It iterates `signal_instance.signal.filters`. It skips any filter that is not `mode == active` and `action == snooze`.

- **No expiration:** a filter with no `expiration` is logged as a warning and skipped.
- **Expired filter:** if `expiration`, treated as UTC, is at or before now, the code does `break`, not `continue`. That ends the loop, so any later snooze filters are not evaluated either.
- **No expression:** a filter with an empty `expression` snoozes every instance of that signal.
- **With expression:** the code builds a query over `SignalInstance` rows with the same `signal_id`. It applies `apply_filter_specific_joins` and `apply_filters` with the expression, then restricts to `SignalInstance.id == signal_instance.id`. If the instance comes back, it is snoozed.
- **Match:** the first match sets `filter_action = snooze` and breaks. No `case_id` is set.

The only time field is the absolute `expiration` datetime. Snooze has no lookback window, and `filter_snooze` has no canary exclusion.

## Deduplication: `filter_dedup`

**Canary:** if `signal_instance.canary` is true, it returns immediately, so a canary is never deduplicated.

**Signal with no filters at all (default dedup):**
- It looks for another instance with the same `signal_id`. The candidate must have a non-null `case_id`, must not be the current instance, and must not be a canary.
- Its `created_at` must be within `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES * 60` seconds before now (`_window_start`).
- The default is 45 minutes, from `dispatch/config.py`, overridable by environment variable.
- It takes the most recent match, newest `created_at` first, and copies its `case_id` onto the instance.
- It sets `filter_action = deduplicate`. Entities are not considered.
- The `filter_signal` docstring says the default window is 1 hour. The code uses 45 minutes.

**Signal with filters:** the default rule does not run. This includes a signal whose only filters are snooze filters or inactive filters.
- Only filters with `mode == active` and `action == deduplicate` are considered.
- For each such filter it queries non-canary instances of the same signal.
- It joins `SignalInstance.entities` and then `Entity.entity_type`, and applies the filter's `expression` with `apply_filters`.
- It requires `created_at >= _window_start(f.window)`. `f.window` is in seconds.
- It joins entities again and requires `Entity.id` to be among the current instance's entity IDs. A candidate must therefore share at least one entity with the current instance.
- It excludes the current instance and orders by `created_at` ascending.
- If any rows come back, the earliest one's `case_id` is copied onto the instance and `filter_action` is set to `deduplicate`.
- The first matching filter wins.
- Unlike the default branch, the filter branch does not require the candidate to have a `case_id`. If the earliest match has none, the instance gets `case_id = None` but is still marked deduplicated.
- A deduplicated instance with no `case_id` is therefore filtered and creates no case.

**Window defaults:**
- The `SignalFilter.window` column defaults to 3600 seconds (1 hour).
- `SignalFilterBase.window` in the pydantic model defaults to 600 seconds (10 minutes).
- Filters created through the API schema therefore get 600 unless the caller sets a value. The column default applies only if no value is passed.
- `window` is not used for snooze.

## Canary signals

- A canary is not deduplicated. `filter_dedup` returns early, and canaries are also excluded as dedup targets in both branches.
- A canary can still be snoozed, because `filter_snooze` has no canary check.
- If it is not snoozed, `signal_instance_create_flow` stores it and returns before case creation, with the comment "limited support for canary signals". No case is created, and no workflows or engagements run.
- Its `filter_action` is `none`.

## Other points

- Only the dedup path updates the signal message. `_should_update_signal_message` is backed by a `TTLCache` (60-second TTL, max 4 entries) keyed by `case_id`. A dedup instance gets a message update when the case has no cache entry. Otherwise it needs at least 5 seconds since the cached instance's `created_at`, plus a `signal_thread_ts` on the case.
- There is also an unrelated `create_signal_instance` in `flows.py`, which only builds the instance through `signal_service.create_instance`. The snooze and dedup decisions happen later, in the processing loop.