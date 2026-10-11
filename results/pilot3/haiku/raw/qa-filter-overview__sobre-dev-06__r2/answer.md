## Decision order for a new signal instance

Everything starts in `signal_instance_create_flow` (`src/dispatch/signal/flows.py:50`). It runs `entity_service.find_entities` first, then calls `signal_service.filter_signal` (`src/dispatch/signal/service.py:867`):

1. **`filter_snooze`** (`service.py:743`) runs first.
2. **`filter_dedup`** (`service.py:788`) runs only if no filter action was set in step 1.
3. If neither set a `filter_action`, it is set to `SignalFilterAction.none`. `filter_signal` returns `True` only when an action was set, and commits.

Back in `signal_instance_create_flow`:

- **Filtered (snoozed or deduplicated):** if the instance has a `case_id` and the case has a conversation, `update_signal_message` may run. It then returns. No case is created and no workflows run.
- **Not filtered:** a canary returns here (see below). If `signal.create_case` is false, it returns. Otherwise it creates a case through `case_service.create`, calls `case_flows.case_new_create_flow`, optionally runs `engage_signal_identity`, and runs the signal's workflows.

## Snooze (`filter_snooze`)

Filters are checked in list order. The first match wins, and the loop exits on it.

- Only filters with `mode == active` and `action == snooze` are considered.
- A snooze filter with no `expiration` is logged as a warning and skipped (`continue`).
- If `expiration` is in the past, the loop **`break`s**. That stops evaluation of all later snooze filters, not just this one. The expiration is treated as UTC: `replace(tzinfo=utc)` is compared with `datetime.now(utc)`.
- If the filter has an `expression`, it is applied with `apply_filter_specific_joins` and `apply_filters` against the signal's instances, and the snooze matches only if this instance's id is in the result. This means the instance's own attributes and entities must satisfy the expression.
- If the expression is empty (`[]`, the Pydantic default), every instance of the signal is snoozed, subject to the expiration check.
- A match sets `filter_action = snooze` and does not set `case_id`.

No time window applies to snooze. The only time check is the expiration.

## Deduplication (`filter_dedup`)

**Canary:** `filter_dedup` returns immediately if `signal_instance.canary` is true.

**Default path (signal has no filters at all, `not signal.filters`):**
- Window: `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` from `src/dispatch/config.py:95`, in **minutes**, default **45**. Converted with `* 60` and passed to `_window_start`.
- Matches any other instance of the same signal created in the window that has a non-null `case_id` and is not canary, regardless of entities.
- Takes the most recent match (`order_by created_at desc`, `.first()`) and copies its `case_id`.
- The docstring for `filter_signal` says 1 hour; the code uses 45 minutes.

**Filter path (signal has at least one filter):**
- Iterates the filters, skipping any that are not `active` or not `deduplicate`. Breaks on the first match.
- Matches instances of the same signal in the window, excluding canary and the instance itself, that share at least one entity with the new instance. The entity match is `Entity.id.in_(...)`. The filter's `expression` is also applied through `apply_filters`.
- Window: `SignalFilter.window`, in **seconds**. The model column default is 3600 (1 hour). The Pydantic `SignalFilterBase.window` default is 600 (10 minutes), which applies when a value is supplied through the schema and not overridden.
- Takes the **earliest** match (`order_by created_at asc`) and copies its `case_id`.

**Consequences of the code as written:**
- If a signal has any filter at all, the 45-minute default path never runs. A signal with only a snooze filter, or only inactive deduplicate filters, gets no deduplication.
- The filter path does not require the matched instance to have a `case_id`, unlike the default path. Snoozed instances have a null `case_id` and are not excluded here. If the earliest match in the window is one of those, the new instance is set to `deduplicate` with `case_id = None`. It is then treated as filtered and no case is created. I read this from the code and did not reproduce it.

## Canary signals

- Snooze is **not** canary-aware. `filter_snooze` runs for canary instances, so a canary can be marked `snooze`. It then returns through the filtered branch.
- Deduplication is skipped for canary instances, and canary instances are excluded from being match targets for other instances (`~SignalInstance.canary`) in both dedup paths.
- A canary that is not snoozed gets `filter_action = none`. `signal_instance_create_flow` then returns at the "limited support for canary signals" check (`flows.py:102`). It creates no case, runs no engagement, and runs no workflows. The instance is stored only.

I traced this statically and did not run the code or the tests.